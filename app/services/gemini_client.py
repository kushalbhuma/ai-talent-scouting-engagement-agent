from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import ProviderRequestError
from app.models.schemas import (
    EvaluationResult,
    ParsedJobDescription,
    RecommendationLabel,
    RetrievalResult,
    ScoreBreakdown,
)

logger = logging.getLogger(__name__)

RECOMMENDATION_LABELS = {
    "Strong Immediate Fit",
    "High Match, Moderate Interest",
    "High Potential, Requires Review",
    "Strong Skills, Lower Alignment",
    "Good Match, Seniority Gap",
    "Moderate Fit",
}


JD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "role": {"type": "string"},
        "must_have_skills": {"type": "array", "items": {"type": "string"}},
        "nice_to_have_skills": {"type": "array", "items": {"type": "string"}},
        "experience_required": {"type": "string"},
        "domain": {"type": "string"},
        "seniority": {"type": "string"},
        "location_preference": {"type": "string"},
        "job_type": {"type": "string"},
    },
    "required": [
        "role",
        "must_have_skills",
        "nice_to_have_skills",
        "experience_required",
        "domain",
        "seniority",
        "location_preference",
        "job_type",
    ],
}


EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "skills_match": {"type": "integer"},
        "experience_match": {"type": "integer"},
        "role_similarity": {"type": "integer"},
        "domain_match": {"type": "integer"},
        "resume_quality": {"type": "integer"},
        "category_match": {"type": "integer"},
        "career_alignment": {"type": "integer"},
        "skill_continuity": {"type": "integer"},
        "transition_plausibility": {"type": "integer"},
        "seniority_fit": {"type": "integer"},
        "domain_preference": {"type": "integer"},
        "recommendation": {
            "type": "string",
            "enum": sorted(RECOMMENDATION_LABELS),
        },
        "reasoning": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "persona_summary": {"type": "string"},
        "simulated_outreach_message": {"type": "string"},
        "simulated_candidate_response": {"type": "string"},
        "interest_reasoning": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "skills_match",
        "experience_match",
        "role_similarity",
        "domain_match",
        "resume_quality",
        "category_match",
        "career_alignment",
        "skill_continuity",
        "transition_plausibility",
        "seniority_fit",
        "domain_preference",
        "recommendation",
        "reasoning",
        "risk_flags",
        "persona_summary",
        "simulated_outreach_message",
        "simulated_candidate_response",
        "interest_reasoning",
    ],
}

# The GeminiClient class provides methods to interact with the Gemini API for parsing job descriptions, generating embeddings, and evaluating candidates. 
# It constructs prompts based on the job description and candidate information, sends requests to the Gemini API, and processes the responses to produce structured evaluation results.
class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.headers = {
            "x-goog-api-key": settings.gemini_api_key or "",
            "Content-Type": "application/json",
        }

    async def parse_job_description(self, text: str) -> ParsedJobDescription:
        prompt = (
            "You are an AI recruiter assistant parsing a job description into a strict schema. "
            "Extract only grounded facts from the JD. Do not invent skills, locations, or seniority. "
            "If a field is missing, return an empty string or empty array.\n\n"
            f"Job Description:\n{text}"
        )
        payload = await self._generate_json(
            prompt=prompt,
            schema=JD_SCHEMA,
            system_instruction=(
                "You convert recruiter job descriptions into a deterministic JSON object "
                "for downstream candidate evaluation."
            ),
        )
        return ParsedJobDescription.model_validate(payload)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=180.0) as client:
            for start in range(0, len(texts), 100):
                chunk = texts[start : start + 100]
                payload = {
                    "requests": [
                        {
                            "model": f"models/{self.settings.gemini_embedding_model}",
                            "content": {"parts": [{"text": text}]},
                        }
                        for text in chunk
                    ]
                }
                response = await self._post(
                    client,
                    f"/models/{self.settings.gemini_embedding_model}:batchEmbedContents",
                    payload,
                )
                for item in response.get("embeddings", []):
                    values = item.get("values") or item.get("embedding", {}).get("values") or []
                    embeddings.append(values)
        return embeddings

    async def evaluate_candidate(
        self,
        jd: ParsedJobDescription,
        retrieval_result: RetrievalResult,
    ) -> EvaluationResult:
        candidate = retrieval_result.candidate
        prompt = f"""
Evaluate this candidate for a recruiter shortlisting workflow.

Locked Match Score formula:
- 35% Skills Match
- 25% Experience Match
- 15% Role Similarity
- 10% Domain Match
- 10% Resume Quality
- 5% Category Match

Locked Interest Likelihood Score formula:
- 35% Career Alignment
- 20% Skill Continuity
- 20% Career Transition Plausibility
- 15% Seniority Fit
- 10% Domain Preference

Evaluation Rules:

1. Evaluate strictly using JD requirements and resume evidence.

2. Score each component independently from 0–100.

3. Skills Match:
- Score based on overlap between JD skills and resume skills.
- Penalize missing must-have skills heavily.

4. Experience Match:
- Compare JD years/seniority against resume experience.
- Penalize clear seniority mismatch.

5. Role Similarity:
- Compare past job titles, responsibilities, and role direction.

6. Domain Match:
- Compare industry/domain relevance.

7. Resume Quality:
- Score clarity, structure, technical depth, and evidence richness.

8. Career Alignment:
- Estimate how aligned this role is with candidate's likely trajectory.

9. Skill Continuity:
- Check if required skills are actively present across recent roles.

10. Transition Plausibility:
- Estimate whether candidate could realistically transition into this role.

11. Seniority Fit:
- Compare candidate level vs JD level.

12. Domain Preference:
- Infer domain alignment only from resume evidence.

13. Use conservative scoring:
- Missing core skills should reduce score significantly.
- Do not over-score partial matches.

14. Keep reasoning grounded and concise.

15. Persona summary must only summarize professional profile.

16. Recruiter outreach should sound realistic and relevant.

17. Candidate response must reflect realistic interest based on resume alignment.

18. Never invent unsupported preferences, motivations, or personality traits.

19. Return deterministic outputs for identical inputs.

Output length guidelines:

- Persona summary: 2–3 concise sentences.
- Recruiter outreach: 1 short recruiter message.
- Candidate response: 1 short realistic reply.
- Reasoning items: concise bullet-style explanations.
- Prefer complete short responses over long explanations.


Parsed JD:
{json.dumps(jd.model_dump(), indent=2)}

Candidate category: {candidate.category}
Candidate inferred metadata:
{json.dumps({
    "skills": candidate.inferred_skills,
    "years_experience": candidate.inferred_years_experience,
    "seniority": candidate.inferred_seniority,
    "role_hint": candidate.inferred_role_hint,
    "domain": candidate.inferred_domain,
    "retrieval_score": retrieval_result.retrieval_score,
    "matched_terms": retrieval_result.matched_terms,
}, indent=2)}

Candidate resume:
{candidate.resume_text[:8000]} #Truncate to respect token limits, but include as much as possible
""".strip()

        payload = await self._generate_json(
            prompt=prompt,
            schema=EVALUATION_SCHEMA,
            system_instruction=(
                "You are a recruiter evaluation engine. Score candidates conservatively, "
                "stay grounded in resume evidence, and provide only structured JSON."
            ),
        )

        breakdown = ScoreBreakdown(
            skills_match=self._clamp(payload["skills_match"]),
            experience_match=self._clamp(payload["experience_match"]),
            role_similarity=self._clamp(payload["role_similarity"]),
            domain_match=self._clamp(payload["domain_match"]),
            resume_quality=self._clamp(payload["resume_quality"]),
            category_match=self._clamp(payload["category_match"]),
            career_alignment=self._clamp(payload["career_alignment"]),
            skill_continuity=self._clamp(payload["skill_continuity"]),
            transition_plausibility=self._clamp(payload["transition_plausibility"]),
            seniority_fit=self._clamp(payload["seniority_fit"]),
            domain_preference=self._clamp(payload["domain_preference"]),
        )

        match_score = round(
            0.35 * breakdown.skills_match
            + 0.25 * breakdown.experience_match
            + 0.15 * breakdown.role_similarity
            + 0.10 * breakdown.domain_match
            + 0.10 * breakdown.resume_quality
            + 0.05 * breakdown.category_match
        )
        interest_score = round(
            0.35 * breakdown.career_alignment
            + 0.20 * breakdown.skill_continuity
            + 0.20 * breakdown.transition_plausibility
            + 0.15 * breakdown.seniority_fit
            + 0.10 * breakdown.domain_preference
        )

        recommendation = payload["recommendation"]
        if recommendation not in RECOMMENDATION_LABELS:
            recommendation = self._derive_recommendation(
                match_score,
                interest_score,
                payload["risk_flags"],
            )

        return EvaluationResult(
            candidate_id=candidate.candidate_id,
            candidate_category=candidate.category,
            match_score=match_score,
            interest_score=interest_score,
            recommendation=recommendation,  # type: ignore[arg-type]
            reasoning=[str(item) for item in payload["reasoning"][:5]],
            risk_flags=[str(item) for item in payload["risk_flags"][:5]],
            persona_summary=str(payload["persona_summary"]),

            simulated_outreach_message=str(payload["simulated_outreach_message"]),
            simulated_candidate_response=str(payload["simulated_candidate_response"]),
            interest_reasoning=[str(item) for item in payload["interest_reasoning"][:5]],
            
            retrieval_score=retrieval_result.retrieval_score,
            score_breakdown=breakdown,
        )

    async def _generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        system_instruction: str,
    ) -> dict[str, Any]:
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0.1, #Low temperature for more deterministic outputs
            },
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await self._post(
                client,
                f"/models/{self.settings.gemini_generation_model}:generateContent",
                payload,
            )
        text = self._extract_text(response)
        return json.loads(text)

    async def _post(
        self,
        client: httpx.AsyncClient,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Gemini request failed: {exc}") from exc

    def _extract_text(self, response: dict[str, Any]) -> str:
        candidates = response.get("candidates", [])
        if not candidates:
            raise ProviderRequestError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        if not text.strip():
            raise ProviderRequestError("Gemini returned an empty response.")
        return text

    def _clamp(self, value: Any) -> int:
        try:
            numeric = int(value)
        except Exception:
            numeric = 0
        return max(0, min(100, numeric))

    def _derive_recommendation(
        self,
        match_score: int,
        interest_score: int,
        risk_flags: list[str],
    ) -> RecommendationLabel:
        if match_score >= 85 and interest_score >= 75 and not risk_flags:
            return "Strong Immediate Fit"
        if match_score >= 80 and interest_score >= 65:
            return "High Match, Moderate Interest"
        if match_score >= 72 and interest_score >= 70:
            return "High Potential, Requires Review"
        if match_score >= 78 and interest_score < 60:
            return "Strong Skills, Lower Alignment"
        if match_score >= 65 and any("seniority" in flag.lower() for flag in risk_flags):
            return "Good Match, Seniority Gap"
        return "Moderate Fit"
