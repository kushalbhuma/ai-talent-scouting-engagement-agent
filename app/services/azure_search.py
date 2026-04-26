from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import ProviderRequestError
from app.models.schemas import CandidateRecord, ParsedJobDescription, RetrievalResult

logger = logging.getLogger(__name__)


class AzureSearchClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = (settings.azure_ai_search_endpoint or "").rstrip("/")
        self.index_name = settings.azure_ai_search_index or ""
        self.api_version = settings.azure_ai_search_api_version
        self.vector_field = settings.azure_ai_search_vector_field
        self.headers = {
            "api-key": settings.azure_ai_search_key or "",
            "Content-Type": "application/json",
        }

    def configured(self) -> bool:
        return bool(self.endpoint and self.index_name and self.headers["api-key"])

    async def ensure_index(self, embedding_dimensions: int) -> None:
        body = {
            "name": self.index_name,
            "fields": [
                {"name": "candidate_id", "type": "Edm.String", "key": True, "searchable": False, "filterable": True, "retrievable": True},
                {"name": "resume_text", "type": "Edm.String", "searchable": True, "retrievable": True},
                {"name": "category", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True, "retrievable": True},
                {"name": "inferred_skills", "type": "Collection(Edm.String)", "searchable": True, "filterable": True, "retrievable": True},
                {"name": "inferred_years_experience", "type": "Edm.Int32", "filterable": True, "sortable": True, "retrievable": True},
                {"name": "inferred_seniority", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
                {"name": "inferred_role_hint", "type": "Edm.String", "searchable": True, "retrievable": True},
                {"name": "inferred_domain", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
                {
                    "name": self.vector_field,
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "retrievable": False,
                    "dimensions": embedding_dimensions,
                    "vectorSearchProfile": "resume-vector-profile",
                },
            ],
            "vectorSearch": {
                "algorithms": [
                    {
                        "name": "resume-hnsw",
                        "kind": "hnsw",
                        "hnswParameters": {
                            "metric": "cosine",
                            "efConstruction": 400,
                            "efSearch": 500,
                            "m": 4,
                        },
                    }
                ],
                "profiles": [
                    {
                        "name": "resume-vector-profile",
                        "algorithm": "resume-hnsw",
                    }
                ],
            },
            "semantic": {
                "configurations": [
                    {
                        "name": "default",
                        "prioritizedFields": {
                            "titleField": {"fieldName": "category"},
                            "prioritizedContentFields": [{"fieldName": "resume_text"}],
                            "prioritizedKeywordsFields": [{"fieldName": "inferred_skills"}],
                        },
                    }
                ]
            },
        }
        await self._put(
            f"/indexes('{self.index_name}')?allowIndexDowntime=true&api-version={self.api_version}",
            body,
            extra_headers={"Prefer": "return=representation"},
        )

    async def get_document_count(self) -> int:
        try:
            response = await self._get(
                f"/indexes('{self.index_name}')/docs/$count?api-version={self.api_version}"
            )
        except ProviderRequestError as exc:
            if "404" in str(exc):
                return 0
            raise
        if isinstance(response, int):
            return response
        if isinstance(response, str) and response.isdigit():
            return int(response)
        return int(response)

    async def upload_candidates(
        self,
        candidates: list[CandidateRecord],
        embeddings: list[list[float]],
    ) -> None:
        if len(candidates) != len(embeddings):
            raise ValueError("Candidate and embedding counts do not match.")

        for start in range(0, len(candidates), 100):
            batch_candidates = candidates[start : start + 100]
            batch_embeddings = embeddings[start : start + 100]
            actions = []
            for candidate, embedding in zip(batch_candidates, batch_embeddings, strict=True):
                actions.append(
                    {
                        "@search.action": "mergeOrUpload",
                        "candidate_id": candidate.candidate_id,
                        "resume_text": candidate.resume_text,
                        "category": candidate.category,
                        "inferred_skills": candidate.inferred_skills,
                        "inferred_years_experience": candidate.inferred_years_experience,
                        "inferred_seniority": candidate.inferred_seniority,
                        "inferred_role_hint": candidate.inferred_role_hint,
                        "inferred_domain": candidate.inferred_domain,
                        self.vector_field: embedding,
                    }
                )
            await self._post(
                f"/indexes('{self.index_name}')/docs/search.index?api-version={self.api_version}",
                {"value": actions},
            )

    async def search(
        self,
        jd: ParsedJobDescription,
        query_vector: list[float],
        top_k: int,
    ) -> list[RetrievalResult]:
        search_text = " ".join(
            [
                jd.role,
                *jd.must_have_skills,
                *jd.nice_to_have_skills,
                jd.domain,
                jd.seniority,
                jd.job_type,
            ]
        ).strip() or "*"
        body = {
            "search": search_text,
            "top": top_k,
            "select": ",".join(
                [
                    "candidate_id",
                    "resume_text",
                    "category",
                    "inferred_skills",
                    "inferred_years_experience",
                    "inferred_seniority",
                    "inferred_role_hint",
                    "inferred_domain",
                ]
            ),
            "queryType": "simple",
            "searchMode": "any",
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_vector,
                    "fields": self.vector_field,
                    "k": top_k,
                    "weight": 2,
                    "exhaustive": True,
                }
            ],
        }
        response = await self._post(
            f"/indexes('{self.index_name}')/docs/search.post.search?api-version={self.api_version}",
            body,
        )
        results: list[RetrievalResult] = []
        for item in response.get("value", []):
            candidate = CandidateRecord(
                candidate_id=str(item.get("candidate_id", "")),
                resume_text=item.get("resume_text", "") or "",
                category=item.get("category", "") or "",
                inferred_skills=item.get("inferred_skills") or [],
                inferred_years_experience=item.get("inferred_years_experience"),
                inferred_seniority=item.get("inferred_seniority", "") or "",
                inferred_role_hint=item.get("inferred_role_hint", "") or "",
                inferred_domain=item.get("inferred_domain", "") or "",
            )
            matched_terms = [term for term in jd.must_have_skills if term in set(candidate.inferred_skills)][:12]
            results.append(
                RetrievalResult(
                    candidate=candidate,
                    retrieval_score=round(float(item.get("@search.score", 0.0)) * 100, 2),
                    matched_terms=matched_terms,
                )
            )
        return results

    async def _get(self, path: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.get(f"{self.endpoint}{path}", headers=self.headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return response.text
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Azure AI Search request failed: {exc}") from exc

    async def _put(
        self,
        path: str,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.put(
                    f"{self.endpoint}{path}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Azure AI Search request failed: {exc}") from exc

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.endpoint}{path}",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Azure AI Search request failed: {exc}") from exc
