from app.models.schemas import JobDescriptionInput
from app.services.jd_parser import JDParser


def test_jd_parser_extracts_core_fields() -> None:
    parser = JDParser()
    result = parser.parse(
        JobDescriptionInput(
            text=(
                "Senior Python Backend Engineer\n"
                "Need 4+ years experience building FastAPI services on Azure. "
                "Remote role in fintech with SQL and Docker."
            )
        )
    )

    assert "python" in result.must_have_skills
    assert result.seniority == "senior"
    assert result.location_preference == "remote"
    assert result.domain == "fintech"
