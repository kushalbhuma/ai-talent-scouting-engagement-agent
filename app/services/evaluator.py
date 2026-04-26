from __future__ import annotations

import re

from app.models.schemas import (
    CandidatePersona,
    EvaluationResult,
    ParsedJobDescription,
    RecommendationLabel,
    RetrievalResult,
    ScoreBreakdown,
)
from app.services.text_utils import bounded_score, normalize_text, overlap_ratio, tokenize


ROLE_HINTS = ["engineer", "developer", "scientist", "analyst", "manager", "architect"]


class CandidateEvaluator:
    def evaluate(
        self,
        jd: ParsedJobDescription,
        retrieval_result: RetrievalResult,
    ) -> EvaluationResult:
        candidate = retrieval_result.candidate
        resume_text = normalize_text(candidate.resume_text)
        resume_tokens = set(tokenize(resume_text))
        jd_skill_tokens = set(jd.must_have_skills + jd.nice_to_have_skills)
        candidate_skill_tokens = set(candidate.inferred_skills)

        skills_match = overlap_ratio(set(jd.must_have_skills), candidate_skill_tokens or resume_tokens) * 100
        experience_match = self._experience_match(
            jd.experience_required,
            candidate.inferred_years_experience,
            resume_text,
        )
        role_similarity = self._role_similarity(
            jd.role,
            resume_tokens | set(tokenize(candidate.inferred_role_hint)),
        )
        domain_match = self._domain_match(jd.domain, candidate.inferred_domain, resume_tokens)
        resume_quality = self._resume_quality(candidate.resume_text)
        category_match = self._category_match(jd.role, candidate.category)

        career_alignment = self._career_alignment(
            jd.role,
            candidate.category,
            resume_tokens | set(tokenize(candidate.inferred_role_hint)),
        )
        skill_continuity = overlap_ratio(jd_skill_tokens, candidate_skill_tokens or resume_tokens) * 100
        transition_plausibility = self._transition_plausibility(jd, resume_tokens, candidate.category)
        seniority_fit = self._seniority_fit(
            jd.seniority,
            candidate.inferred_seniority,
            resume_text,
        )
        domain_preference = 100.0 if jd.domain and jd.domain == candidate.inferred_domain else 50.0 if not jd.domain else 40.0

        match_score = round(
            0.35 * skills_match
            + 0.25 * experience_match
            + 0.15 * role_similarity
            + 0.10 * domain_match
            + 0.10 * resume_quality
            + 0.05 * category_match
        )
        interest_score = round(
            0.35 * career_alignment
            + 0.20 * skill_continuity
            + 0.20 * transition_plausibility
            + 0.15 * seniority_fit
            + 0.10 * domain_preference
        )

        persona = self._infer_persona(candidate.resume_text)
        reasoning = self._reasoning(jd, retrieval_result, candidate.category, persona)
        risk_flags = self._risk_flags(jd, skills_match, experience_match, seniority_fit, domain_match)
        recommendation = self._recommend(match_score, interest_score, risk_flags)

        return EvaluationResult(
            candidate_id=candidate.candidate_id,
            candidate_category=candidate.category,
            match_score=match_score,
            interest_score=interest_score,
            recommendation=recommendation,
            reasoning=reasoning,
            risk_flags=risk_flags,
            persona_summary=persona.summary,
            retrieval_score=retrieval_result.retrieval_score,
            score_breakdown=ScoreBreakdown(
                skills_match=round(skills_match, 2),
                experience_match=round(experience_match, 2),
                role_similarity=round(role_similarity, 2),
                domain_match=round(domain_match, 2),
                resume_quality=round(resume_quality, 2),
                category_match=round(category_match, 2),
                career_alignment=round(career_alignment, 2),
                skill_continuity=round(skill_continuity, 2),
                transition_plausibility=round(transition_plausibility, 2),
                seniority_fit=round(seniority_fit, 2),
                domain_preference=round(domain_preference, 2),
            ),
        )

    def _experience_match(
        self,
        experience_required: str,
        inferred_years: int | None,
        resume_text: str,
    ) -> float:
        if not experience_required:
            return 60.0
        required = re.search(r"(\d+)", experience_required)
        if not required or inferred_years is None:
            return 45.0
        required_years = int(required.group(1))
        observed_years = inferred_years
        ratio = min(observed_years / max(required_years, 1), 1.2)
        return bounded_score(ratio * 85)

    def _role_similarity(self, role: str, resume_tokens: set[str]) -> float:
        if not role or role == "Unspecified Role":
            return 50.0
        role_terms = set(tokenize(role))
        return overlap_ratio(role_terms, resume_tokens) * 100

    def _resume_quality(self, resume_text: str) -> float:
        token_count = len(tokenize(resume_text))
        if token_count > 250:
            return 90.0
        if token_count > 150:
            return 75.0
        if token_count > 80:
            return 60.0
        return 40.0

    def _domain_match(self, jd_domain: str, candidate_domain: str, resume_tokens: set[str]) -> float:
        if not jd_domain:
            return 40.0
        if jd_domain == candidate_domain:
            return 100.0
        if jd_domain in resume_tokens:
            return 75.0
        return 0.0

    def _category_match(self, role: str, category: str) -> float:
        role_tokens = set(tokenize(role))
        category_tokens = set(tokenize(category))
        if not category_tokens:
            return 40.0
        return overlap_ratio(role_tokens, category_tokens) * 100

    def _career_alignment(self, role: str, category: str, resume_tokens: set[str]) -> float:
        role_tokens = set(tokenize(role))
        category_tokens = set(tokenize(category))
        combined = category_tokens | resume_tokens
        return overlap_ratio(role_tokens, combined) * 100 if role_tokens else 55.0

    def _transition_plausibility(
        self,
        jd: ParsedJobDescription,
        resume_tokens: set[str],
        category: str,
    ) -> float:
        relevant_terms = set(tokenize(jd.role)) | set(jd.must_have_skills) | set(tokenize(category))
        overlap = overlap_ratio(relevant_terms, resume_tokens) * 100
        return max(overlap, 35.0)

    def _seniority_fit(self, seniority: str, inferred_seniority: str, resume_text: str) -> float:
        lowered = resume_text.lower()
        if not seniority:
            return 60.0
        if seniority == inferred_seniority or seniority in lowered:
            return 95.0
        if seniority == "senior" and any(word in lowered for word in ["lead", "staff", "principal"]):
            return 88.0
        if seniority in {"junior", "mid"} and "senior" in lowered:
            return 55.0
        return 45.0

    def _infer_persona(self, resume_text: str) -> CandidatePersona:
        sentences = [part.strip() for part in re.split(r"[.\n]", resume_text) if part.strip()]
        evidence = sentences[:3]
        role_bits = [sentence for sentence in evidence if any(hint in sentence.lower() for hint in ROLE_HINTS)]
        summary = role_bits[0] if role_bits else "Candidate shows relevant technical background from resume evidence."
        return CandidatePersona(summary=summary[:180], evidence=evidence[:3])

    def _reasoning(
        self,
        jd: ParsedJobDescription,
        retrieval_result: RetrievalResult,
        category: str,
        persona: CandidatePersona,
    ) -> list[str]:
        reasons = []
        if retrieval_result.matched_terms:
            reasons.append(
                "Matched core terms: " + ", ".join(retrieval_result.matched_terms[:5])
            )
        if jd.role:
            reasons.append(f"Role alignment assessed against target role: {jd.role}.")
        if category:
            reasons.append(f"Resume category suggests prior trajectory in {category}.")
        reasons.append(f"Persona evidence: {persona.summary}")
        return reasons[:4]

    def _risk_flags(
        self,
        jd: ParsedJobDescription,
        skills_match: float,
        experience_match: float,
        seniority_fit: float,
        domain_match: float,
    ) -> list[str]:
        flags = []
        if jd.must_have_skills and skills_match < 50:
            flags.append("Limited alignment on required skills.")
        if jd.experience_required and experience_match < 55:
            flags.append("Experience evidence is weaker than the JD target.")
        if jd.seniority and seniority_fit < 60:
            flags.append("Possible seniority mismatch.")
        if jd.domain and domain_match < 50:
            flags.append("Domain evidence is limited in the resume.")
        return flags

    def _recommend(
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
