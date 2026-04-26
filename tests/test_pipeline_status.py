from app.services.pipeline import RecruiterPipeline


def test_search_index_status_requires_credentials_for_provider_mode() -> None:
    status = RecruiterPipeline().search_index_status()

    assert status.backend == "unconfigured"
    assert status.configured is False
    assert status.ready is False
