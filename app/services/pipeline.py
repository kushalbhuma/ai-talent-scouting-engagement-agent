from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from app.core.config import get_settings
from app.core.exceptions import (
    AgentConfigurationError,
    ProviderRequestError,
    SearchIndexNotReadyError,
)
from app.models.schemas import (
    DatasetSummary,
    ResultListResponse,
    SearchIndexStatus,
    ShortlistRequest,
    ShortlistResult,
)
from app.services.adapters import (
    get_llm_backend_name,
    get_retrieval_backend_name,
    is_azure_search_enabled,
    is_gemini_enabled,
)
from app.services.azure_search import AzureSearchClient
from app.services.document_parser import DocumentParser
from app.services.gemini_client import GeminiClient
from app.services.resume_repository import ResumeRepository
from app.services.storage import ResultStore

logger = logging.getLogger(__name__)


class RecruiterPipeline:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.document_parser = DocumentParser()
        self.resume_repository = ResumeRepository(settings.resume_data_path)
        self.result_store = ResultStore(settings.sqlite_db_path)
        self.gemini_client = GeminiClient(settings) if is_gemini_enabled(settings) else None
        self.azure_search_client = (
            AzureSearchClient(settings) if is_azure_search_enabled(settings) else None
        )

    async def run(self, payload: ShortlistRequest) -> ShortlistResult:
        if not isinstance(payload, ShortlistRequest):
            payload = ShortlistRequest.model_validate(payload)
        logger.info("Starting shortlist pipeline")
        self._require_provider_configuration()
        parsed_jd = await self._parse_jd(payload.jd.text)
        candidates = await asyncio.to_thread(self.resume_repository.load_candidates)
        retrieved = await self._retrieve_candidates(parsed_jd, candidates)
        if not retrieved:
            raise ValueError("No candidates matched the JD. Try a broader description.")

        evaluated = []

        for result in retrieved[: self.settings.top_k_evaluation]:

            candidate_eval = None

            for attempt in range(3): # Retry evaluation up to 3 times in case of transient errors (e.g., rate limits, timeouts)
                try:
                    candidate_eval = await self._evaluate_candidate(parsed_jd, result)
                    break

                except Exception as exc:
                    logger.warning(
                        "Candidate evaluation retry %s failed: %s",
                        attempt + 1,
                        exc,
                    )
                    await asyncio.sleep(5*(attempt + 1)) # Wait before retrying (5s, 10s, 15s)

            if candidate_eval:
                evaluated.append(candidate_eval)
            else:
                logger.warning(
                    "Candidate evaluation skipped after retries for candidate: %s",
                    result.candidate.candidate_id,
                )

            await asyncio.sleep(3)  # To respect rate limits
        for item in evaluated:
            item.final_score = (
                (item.match_score * 0.60)
                + (item.interest_score * 0.20)
                + (item.retrieval_score * 0.20)
            )

        evaluated.sort(
            key=lambda item: item.final_score,
            reverse=True,
        )

        try:
            shortlist = ShortlistResult(
                request_id=str(uuid4()),
                created_at=datetime.now(timezone.utc),
                jd=parsed_jd,
                candidates=evaluated,
                total_candidates_scanned=len(candidates),
                retrieval_candidates_considered=len(retrieved),
                retrieval_backend=get_retrieval_backend_name(self.settings),
                llm_backend=get_llm_backend_name(self.settings),
            )
        except Exception as exc:
            logger.exception("ShortlistResult validation failed")
            raise
        try:
            await asyncio.to_thread(self.result_store.save, shortlist)
        except Exception as exc:
            logger.exception("Result store save failed: %s", exc)
            raise ValueError(f"Result store save failed: {exc}")

        logger.info("Shortlist pipeline finished with %s candidates", len(evaluated))
        return shortlist

    def list_results(self) -> ResultListResponse:
        return self.result_store.list_results()

    async def run_from_jd_file(self, file_path: str) -> ShortlistResult:
        jd_text = await asyncio.to_thread(self.document_parser.parse, file_path)
        return await self.run(ShortlistRequest(jd={"text": jd_text}))

    def dataset_summary(self) -> DatasetSummary:
        return self.resume_repository.summarize()

    async def search_index_status(self) -> SearchIndexStatus:
        configured = self.azure_search_client is not None
        if not configured:
            return SearchIndexStatus(
                index_name=self.settings.azure_ai_search_index or "",
                backend="unconfigured",
                configured=False,
                ready=False,
                message="Azure AI Search is not configured. Add .env credentials before running the agent.",
                last_sync_fingerprint=self.result_store.get_state("azure_search_index_fingerprint"),
            )

        document_count = 0
        ready = False
        message = "Azure AI Search is configured but not yet verified."
        try:
            document_count = await self.azure_search_client.get_document_count()
            ready = document_count > 0
            message = "Azure AI Search index reachable."
        except Exception as exc:
            message = f"Azure AI Search check failed: {exc}"

        return SearchIndexStatus(
            index_name=self.settings.azure_ai_search_index or "",
            backend="azure_ai_search",
            configured=True,
            ready=ready,
            document_count=document_count,
            last_sync_fingerprint=self.result_store.get_state("azure_search_index_fingerprint"),
            message=message,
        )

    async def sync_search_index(self, force: bool = False) -> SearchIndexStatus:
        self._require_provider_configuration()
        candidates = await asyncio.to_thread(self.resume_repository.load_candidates)
        await self._ensure_search_index(candidates, force=force)
        return await self.search_index_status()

    async def _parse_jd(self, jd_text: str):
        if not self.gemini_client:
            raise AgentConfigurationError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
        return await self.gemini_client.parse_job_description(jd_text)

    async def _retrieve_candidates(self, parsed_jd, candidates):
        if not self.azure_search_client or not self.gemini_client:
            raise AgentConfigurationError(
                "Azure AI Search or Gemini is not configured. Add provider credentials to .env."
            )
        
        query_text = " ".join(
            [
                parsed_jd.role,
                *parsed_jd.must_have_skills,
                *parsed_jd.nice_to_have_skills,
                parsed_jd.domain,
                parsed_jd.seniority,
            ]
        ).strip() or parsed_jd.role or "candidate search"
        query_embeddings = await self.gemini_client.embed_texts([query_text])
        if not query_embeddings:
            raise ProviderRequestError("Gemini did not return a query embedding for candidate retrieval.")
        results = await self.azure_search_client.search(
            jd=parsed_jd,
            query_vector=query_embeddings[0],
            top_k=self.settings.top_k_retrieval,
        )
        return results

    async def _evaluate_candidate(self, parsed_jd, result):
        if not self.gemini_client:
            raise AgentConfigurationError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
        return await self.gemini_client.evaluate_candidate(parsed_jd, result)

    async def _ensure_search_index(self, candidates, force: bool = False) -> None:
        if not self.azure_search_client or not self.gemini_client:
            raise AgentConfigurationError(
                "Azure AI Search or Gemini is not configured. Add provider credentials to .env."
            )

        current_fingerprint = await asyncio.to_thread(self.resume_repository.dataset_fingerprint)
        previous_fingerprint = await asyncio.to_thread(
            self.result_store.get_state,
            "azure_search_index_fingerprint",
        )
        current_count = await self.azure_search_client.get_document_count()
        needs_sync = (
            force
            or previous_fingerprint != current_fingerprint
            or current_count != len(candidates)
        )
        if not needs_sync:
            return

        logger.info("Syncing Azure AI Search index '%s' with %s candidates", self.settings.azure_ai_search_index, len(candidates))
        
        # inorder to save token quota (free-tier limitations), we are only embedding the first 2500 characters of the resume for index creation. 
        #This should be sufficient for relevance matching in most cases, but can be adjusted as needed.
        sample_embeddings = await self.gemini_client.embed_texts([candidates[0].resume_text[:2500]]) 
        if not sample_embeddings:
            raise ProviderRequestError("Gemini did not return an embedding for index creation.")
        await self.azure_search_client.ensure_index(len(sample_embeddings[0]))
        
        embeddings = []

        # Embedding in batches to manage memory and respect rate limits. 
        # Adjust batch size as needed based on resume lengths and token limits.
        batch_size = 5

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]

            batch_embeddings = await self.gemini_client.embed_texts(
                #Embedding only the first 2500 characters of the resume to manage token limits and costs (free-tier limitations). 
                # Adjust as needed.
                [candidate.resume_text[:2500] for candidate in batch]
            )

            embeddings.extend(batch_embeddings)

            await asyncio.sleep(8)  # To respect rate limits

        await self.azure_search_client.upload_candidates(candidates, embeddings)
        await asyncio.to_thread(
            self.result_store.set_state,
            "azure_search_index_fingerprint",
            current_fingerprint,
        )
        logger.info("Azure AI Search sync complete")

    def _require_provider_configuration(self) -> None:
        missing = []
        if not self.settings.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if not self.settings.azure_ai_search_endpoint:
            missing.append("AZURE_AI_SEARCH_ENDPOINT")
        if not self.settings.azure_ai_search_key:
            missing.append("AZURE_AI_SEARCH_KEY")
        if not self.settings.azure_ai_search_index:
            missing.append("AZURE_AI_SEARCH_INDEX")
        if missing:
            raise AgentConfigurationError(
                "Production providers are required for this agent. Missing .env values: "
                + ", ".join(missing)
            )


@lru_cache(maxsize=1)
def get_pipeline() -> RecruiterPipeline:
    return RecruiterPipeline()
