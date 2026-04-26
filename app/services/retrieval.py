from __future__ import annotations

from app.models.schemas import CandidateRecord, ParsedJobDescription, RetrievalResult
from app.services.text_utils import overlap_ratio, term_frequency, tokenize


TECHNICAL_ROLE_TERMS = {
    "engineer",
    "developer",
    "scientist",
    "analyst",
    "architect",
    "devops",
    "platform",
}

# The CandidateRetriever class implements the retrieval logic for finding relevant candidates based on a parsed job description. 
class CandidateRetriever:
    def retrieve(
        self,
        jd: ParsedJobDescription,
        candidates: list[CandidateRecord],
        top_k: int,
    ) -> list[RetrievalResult]:
        jd_terms = set(
            tokenize(
                " ".join(
                    [
                        jd.role,
                        *jd.must_have_skills,
                        *jd.nice_to_have_skills,
                        jd.domain,
                        jd.seniority,
                        jd.job_type,
                    ]
                )
            )
        )
        scored: list[RetrievalResult] = []

        for candidate in candidates:
            candidate_terms = set(term_frequency(candidate.resume_text).keys())
            role_terms = set(tokenize(candidate.inferred_role_hint or candidate.category))
            skill_terms = set(candidate.inferred_skills)
            domain_terms = set(tokenize(candidate.inferred_domain))
            jd_role_terms = set(tokenize(jd.role))
            skill_overlap = set(jd.must_have_skills + jd.nice_to_have_skills) & (skill_terms or candidate_terms)

            lexical_score = overlap_ratio(
                jd_terms or set(tokenize(candidate.category)),
                candidate_terms,
            ) * 100
            role_score = overlap_ratio(jd_role_terms, role_terms or candidate_terms) * 100
            skill_score = overlap_ratio(
                set(jd.must_have_skills + jd.nice_to_have_skills),
                skill_terms or candidate_terms,
            ) * 100
            domain_score = 100.0 if jd.domain and jd.domain in domain_terms else 35.0 if not jd.domain else 0.0
            category_bonus = 0.0
            if TECHNICAL_ROLE_TERMS & jd_role_terms and candidate.category.upper() in {
                "INFORMATION-TECHNOLOGY",
                "ENGINEERING",
                "DATA SCIENCE",
                "DEVOPS ENGINEER",
            }:
                category_bonus = 8.0
            if jd.must_have_skills and not skill_overlap and role_score < 30:
                continue
            if TECHNICAL_ROLE_TERMS & jd_role_terms and not skill_terms and role_score < 35:
                continue
            score = (
                0.45 * lexical_score
                + 0.25 * skill_score
                + 0.20 * role_score
                + 0.10 * domain_score
                + category_bonus
            )
            matched_terms = sorted(
                (jd_terms & candidate_terms) | skill_overlap
            )[:12]
            if score <= 0:
                continue
            scored.append(
                RetrievalResult(
                    candidate=candidate,
                    retrieval_score=round(score, 2),
                    matched_terms=matched_terms,
                )
            )

        scored.sort(key=lambda item: item.retrieval_score, reverse=True)
        return scored[:top_k]
