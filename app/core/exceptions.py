class AgentConfigurationError(RuntimeError):
    """Raised when required provider configuration is missing."""


class ProviderRequestError(RuntimeError):
    """Raised when an external AI/search provider request fails."""


class SearchIndexNotReadyError(RuntimeError):
    """Raised when Azure AI Search is configured but not ready for use."""
