from fastapi import FastAPI

from app.api.routes import router
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(
    title="Talent Scouting & Engagement Agent",
    version="0.1.0",
    description=(
        "AI recruiter evaluation engine for explainable candidate shortlisting."
    ),
)

app.include_router(router)
