from __future__ import annotations

import re

from app.models.schemas import JobDescriptionInput, ParsedJobDescription
from app.services.text_utils import tokenize


KNOWN_SKILLS = {
    "python",
    "java",
    "sql",
    "fastapi",
    "streamlit",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "react",
    "node",
    "tensorflow",
    "pytorch",
    "nlp",
    "llm",
    "machine",
    "learning",
    "data",
    "spark",
    "airflow",
}

ROLE_PATTERNS = [
    "backend engineer",
    "software engineer",
    "python developer",
    "java developer",
    "data scientist",
    "data analyst",
    "machine learning engineer",
    "devops engineer",
    "platform engineer",
    "product manager",
    "project manager",
    "hr specialist",
    "hr manager",
    "recruiter",
]

SENIORITY_KEYWORDS = ["intern", "junior", "mid", "senior", "lead", "staff", "principal"]
JOB_TYPE_KEYWORDS = ["remote", "hybrid", "onsite", "full-time", "contract", "internship"]
DOMAIN_KEYWORDS = [
    "healthcare",
    "finance",
    "fintech",
    "ecommerce",
    "saas",
    "education",
    "marketing",
    "cloud",
    "ai",
    "ml",
]


class JDParser:
    """Heuristic parser until Gemini structured extraction is wired in."""

    def parse(self, jd_input: JobDescriptionInput) -> ParsedJobDescription:
        text = jd_input.text.strip()
        tokens = tokenize(text)
        token_set = set(tokens)

        role = self._extract_role(text)
        must_have = sorted(skill for skill in KNOWN_SKILLS if skill in token_set)[:8]
        nice_to_have = sorted(
            skill
            for skill in {"docker", "kubernetes", "azure", "aws", "nlp", "llm"}
            if skill in token_set and skill not in must_have
        )
        experience_required = self._extract_experience(text)
        domain = next((item for item in DOMAIN_KEYWORDS if item in token_set), "")
        seniority = next((item for item in SENIORITY_KEYWORDS if item in token_set), "")
        location_preference = self._extract_location(text)
        job_type = next(
            (item for item in JOB_TYPE_KEYWORDS if item in text.lower()),
            "",
        )

        return ParsedJobDescription(
            role=role,
            must_have_skills=must_have,
            nice_to_have_skills=nice_to_have,
            experience_required=experience_required,
            domain=domain,
            seniority=seniority,
            location_preference=location_preference,
            job_type=job_type,
        )

    def _extract_role(self, text: str) -> str:
        lowered = text.lower()
        for pattern in ROLE_PATTERNS:
            if pattern in lowered:
                seniority = next((item for item in SENIORITY_KEYWORDS if item in lowered), "")
                return f"{seniority} {pattern}".strip().title()

        lines = [line.strip(" :-") for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            line_lowered = line.lower()
            if any(
                keyword in line_lowered
                for keyword in ["engineer", "developer", "scientist", "analyst", "manager"]
            ):
                cleaned = re.split(r"\bwith\b|\bneed\b|\brequired\b|\bexperience\b", line, maxsplit=1, flags=re.IGNORECASE)[0]
                return cleaned.strip(" :-")
        match = re.search(
            r"(senior|junior|lead|staff|principal)?\s*([A-Za-z/ ]{3,40})(engineer|developer|scientist|analyst|manager)",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(0).strip() if match else "Unspecified Role"

    def _extract_experience(self, text: str) -> str:
        match = re.search(r"(\d+\+?\s*(?:years|yrs).{0,20}experience)", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_location(self, text: str) -> str:
        lowered = text.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        if "onsite" in lowered:
            return "onsite"
        return ""
