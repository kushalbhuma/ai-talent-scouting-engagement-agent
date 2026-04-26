from __future__ import annotations

from app.core.config import Settings


def get_retrieval_backend_name(settings: Settings) -> str:
    if (
        settings.gemini_api_key
        and settings.azure_ai_search_endpoint
        and settings.azure_ai_search_key
        and settings.azure_ai_search_index
    ):
        return "azure_ai_search"
    return "unconfigured"


def get_llm_backend_name(settings: Settings) -> str:
    if settings.gemini_api_key:
        return "gemini"
    return "unconfigured"


def is_gemini_enabled(settings: Settings) -> bool:
    return bool(settings.gemini_api_key)


def is_azure_search_enabled(settings: Settings) -> bool:
    return bool(
        settings.gemini_api_key
        and settings.azure_ai_search_endpoint
        and settings.azure_ai_search_key
        and settings.azure_ai_search_index
    )
