from app.models.schemas import CandidateRecord, ParsedJobDescription, RetrievalResult
from app.services.evaluator import CandidateEvaluator


def test_evaluator_returns_bounded_scores() -> None:
    evaluator = CandidateEvaluator()
    jd = ParsedJobDescription(
        role="Senior Python Backend Engineer",
        must_have_skills=["python", "fastapi", "sql"],
        experience_required="4 years experience",
        domain="fintech",
        seniority="senior",
    )
    result = evaluator.evaluate(
        jd,
        RetrievalResult(
            candidate=CandidateRecord(
                candidate_id="candidate-1",
                category="Python Developer",
                resume_text=(
                    "Senior Python developer with 5 years experience. "
                    "Built FastAPI APIs, SQL services, and fintech platforms on Azure."
                ),
            ),
            retrieval_score=88.0,
            matched_terms=["python", "fastapi", "sql"],
        ),
    )

    assert 0 <= result.match_score <= 100
    assert 0 <= result.interest_score <= 100
    assert result.recommendation
