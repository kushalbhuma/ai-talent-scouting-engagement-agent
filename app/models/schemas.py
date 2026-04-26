from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RecommendationLabel = Literal[
    "Strong Immediate Fit",
    "High Match, Moderate Interest",
    "High Potential, Requires Review",
    "Strong Skills, Lower Alignment",
    "Good Match, Seniority Gap",
    "Moderate Fit",
]


class HealthResponse(BaseModel):
    status: str


class JobDescriptionInput(BaseModel):
    text: str = Field(min_length=20, description="Raw job description text")


class ParsedJobDescription(BaseModel):
    role: str = ""
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    experience_required: str = ""
    domain: str = ""
    seniority: str = ""
    location_preference: str = ""
    job_type: str = ""


class CandidateRecord(BaseModel):
    candidate_id: str
    resume_text: str
    resume_html: str = ""
    category: str = ""
    inferred_skills: list[str] = Field(default_factory=list)
    inferred_years_experience: int | None = None
    inferred_seniority: str = ""
    inferred_role_hint: str = ""
    inferred_domain: str = ""


class CandidatePersona(BaseModel):
    summary: str
    evidence: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    candidate: CandidateRecord
    retrieval_score: float
    matched_terms: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    skills_match: float
    experience_match: float
    role_similarity: float
    domain_match: float
    resume_quality: float
    category_match: float
    career_alignment: float
    skill_continuity: float
    transition_plausibility: float
    seniority_fit: float
    domain_preference: float


class EvaluationResult(BaseModel):
    candidate_id: str
    candidate_category: str
    match_score: int
    interest_score: int
    final_score: float | None = None
    recommendation: RecommendationLabel
    reasoning: list[str]
    risk_flags: list[str]
    persona_summary: str

    simulated_outreach_message: str = ""
    simulated_candidate_response: str = ""
    interest_reasoning: list[str] = Field(default_factory=list)
    
    retrieval_score: float
    score_breakdown: ScoreBreakdown


class ShortlistResult(BaseModel):
    request_id: str
    created_at: datetime
    jd: ParsedJobDescription
    candidates: list[EvaluationResult]
    total_candidates_scanned: int = 0
    retrieval_candidates_considered: int = 0
    retrieval_backend: str = "local"
    llm_backend: str = "heuristic"


class ResultRow(BaseModel):
    request_id: str
    created_at: datetime
    role: str
    top_candidate_id: str | None = None
    top_recommendation: str | None = None


class ResultListResponse(BaseModel):
    items: list[ResultRow]


class ShortlistRequest(BaseModel):
    jd: JobDescriptionInput


class DatasetSummary(BaseModel):
    total_candidates: int
    categories: list[str]
    top_skills: list[str]


class SearchIndexStatus(BaseModel):
    index_name: str
    backend: str
    configured: bool
    ready: bool
    document_count: int = 0
    last_sync_fingerprint: str | None = None
    message: str = ""


class SearchIndexSyncResponse(BaseModel):
    status: SearchIndexStatus
