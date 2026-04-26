import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions import (
    AgentConfigurationError,
    ProviderRequestError,
    SearchIndexNotReadyError,
)
from app.models.schemas import (
    DatasetSummary,
    HealthResponse,
    ResultListResponse,
    SearchIndexStatus,
    SearchIndexSyncResponse,
    ShortlistRequest,
    ShortlistResult,
)
from app.services.pipeline import RecruiterPipeline, get_pipeline

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")

# The create_shortlist endpoint is the main entry point for creating a candidate shortlist based on a provided job description. 
@router.post("/api/v1/shortlist", response_model=ShortlistResult)
async def create_shortlist(
    payload: ShortlistRequest,
    pipeline: RecruiterPipeline = Depends(get_pipeline),
):
    try:
        return await pipeline.run(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        logging.exception("ValueError inside shortlist endpoint")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SearchIndexNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected shortlist endpoint failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/results", response_model=ResultListResponse)
def list_results(
    pipeline: RecruiterPipeline = Depends(get_pipeline),
) -> ResultListResponse:
    return pipeline.list_results()


@router.get("/api/v1/dataset-summary", response_model=DatasetSummary)
def dataset_summary(
    pipeline: RecruiterPipeline = Depends(get_pipeline),
) -> DatasetSummary:
    return pipeline.dataset_summary()


@router.get("/api/v1/search-index-status", response_model=SearchIndexStatus)
async def search_index_status(
    pipeline: RecruiterPipeline = Depends(get_pipeline),
) -> SearchIndexStatus:
    return await pipeline.search_index_status()


@router.post("/api/v1/admin/sync-search-index", response_model=SearchIndexSyncResponse)
async def sync_search_index(
    force: bool = False,
    pipeline: RecruiterPipeline = Depends(get_pipeline),
) -> SearchIndexSyncResponse:
    try:
        return SearchIndexSyncResponse(status=await pipeline.sync_search_index(force=force))
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
