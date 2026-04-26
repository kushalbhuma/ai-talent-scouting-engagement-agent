import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Note: We avoid using python-dotenv to reduce dependencies and have more control over env loading behavior. This function will load environment variables from a .env file if it exists, without overriding existing environment variables.
def _load_dotenv() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

# Utility function to resolve paths relative to the project root. This allows users to specify either absolute paths or paths relative to the project root in environment variables.
def _resolve_project_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())

#  Settings class using Pydantic for validation and type enforcement. This class defines all the configuration options for the application, with default values and types. The get_settings function loads the environment variables and returns a Settings instance, caching it for future use.
class Settings(BaseModel):
    app_name: str = "Talent Scouting & Engagement Agent"
    environment: str = "development"
    project_root: str = str(PROJECT_ROOT)
    sqlite_db_path: str = str((PROJECT_ROOT / "app.db").resolve())
    resume_data_path: str = str((PROJECT_ROOT / "data" / "Resume.csv").resolve())
    logs_dir: str = str((PROJECT_ROOT / "logs").resolve())
    top_k_retrieval: int = 15
    top_k_evaluation: int = 5
    api_host: str = "127.0.0.1"
    api_port: int = 8010
    streamlit_host: str = "127.0.0.1"
    streamlit_port: int = 8510
    backend_api_url: str = "http://127.0.0.1:8010"
    gemini_api_key: str | None = None
    gemini_generation_model: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "gemini-embedding-001"
    azure_ai_search_endpoint: str | None = None
    azure_ai_search_key: str | None = None
    azure_ai_search_index: str | None = None
    azure_ai_search_api_version: str = "2024-07-01"
    azure_ai_search_vector_field: str = "resume_embedding"
    azure_ai_search_force_reindex: bool = False

# The get_settings function is decorated with lru_cache to ensure that the settings are loaded and parsed only once, improving performance by avoiding redundant work on subsequent calls.
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        sqlite_db_path=_resolve_project_path(os.getenv("SQLITE_DB_PATH", "app.db")),
        resume_data_path=_resolve_project_path(os.getenv("RESUME_DATA_PATH", "data/Resume.csv")),
        logs_dir=_resolve_project_path(os.getenv("LOGS_DIR", "logs")),
        top_k_retrieval=int(os.getenv("TOP_K_RETRIEVAL", "15")),
        top_k_evaluation=int(os.getenv("TOP_K_EVALUATION", "5")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8010")),
        streamlit_host=os.getenv("STREAMLIT_HOST", "127.0.0.1"),
        streamlit_port=int(os.getenv("STREAMLIT_PORT", "8510")),
        backend_api_url=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8010"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_generation_model=os.getenv("GEMINI_GENERATION_MODEL", "gemini-1.5-pro"),
        gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        azure_ai_search_endpoint=os.getenv("AZURE_AI_SEARCH_ENDPOINT"),
        azure_ai_search_key=os.getenv("AZURE_AI_SEARCH_KEY"),
        azure_ai_search_index=os.getenv("AZURE_AI_SEARCH_INDEX"),
        azure_ai_search_api_version=os.getenv("AZURE_AI_SEARCH_API_VERSION", "2024-07-01"),
        azure_ai_search_vector_field=os.getenv("AZURE_AI_SEARCH_VECTOR_FIELD", "resume_embedding"),
        azure_ai_search_force_reindex=os.getenv("AZURE_AI_SEARCH_FORCE_REINDEX", "false").lower() == "true",
    )
