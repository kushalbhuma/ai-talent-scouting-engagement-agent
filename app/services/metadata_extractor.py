from __future__ import annotations

import re

from app.services.text_utils import tokenize


KNOWN_SKILLS = {
    "python",
    "java",
    "sql",
    "fastapi",
    "flask",
    "django",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "react",
    "node",
    "javascript",
    "typescript",
    "tensorflow",
    "pytorch",
    "nlp",
    "llm",
    "machine",
    "learning",
    "spark",
    "airflow",
    "powerbi",
    "tableau",
    "salesforce",
    "hris",
    "recruiting",
}

ROLE_PATTERNS = [
    "backend engineer",
    "software engineer",
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

DOMAIN_TERMS = [
    "healthcare",
    "finance",
    "fintech",
    "ecommerce",
    "saas",
    "education",
    "marketing",
    "hospitality",
    "payments",
    "cloud",
]

SENIORITY_TERMS = [
    "intern",
    "junior",
    "mid",
    "senior",
    "lead",
    "staff",
    "principal",
    "director",
    "manager",
]


def strip_html(raw: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", raw or "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_skills(text: str) -> list[str]:
    tokens = set(tokenize(text))
    return sorted(skill for skill in KNOWN_SKILLS if skill in tokens)


def extract_years_experience(text: str) -> int | None:
    matches = re.findall(r"(\d+)\+?\s*(?:years|yrs)", text.lower())
    if not matches:
        return None
    return max(int(value) for value in matches)


def infer_seniority(text: str) -> str:
    lowered = text.lower()
    for term in reversed(SENIORITY_TERMS):
        if term in lowered:
            return term
    return ""


def infer_role(text: str) -> str:
    lowered = text.lower()
    for pattern in ROLE_PATTERNS:
        if pattern in lowered:
            return pattern.title()
    return ""


def infer_domain(text: str) -> str:
    lowered = text.lower()
    for term in DOMAIN_TERMS:
        if term in lowered:
            return term
    return ""
