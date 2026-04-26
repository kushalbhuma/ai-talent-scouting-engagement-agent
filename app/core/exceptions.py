# This module defines custom exceptions used throughout the application to represent specific error conditions related to agent configuration, provider requests, and search index readiness. These exceptions allow for more granular error handling and clearer communication of issues to the client in the API routes.
class AgentConfigurationError(RuntimeError):
    """Raised when required provider configuration is missing."""

# These custom exceptions allow us to raise specific errors in our application that can be caught and handled appropriately in the API routes, providing clearer error messages to the client and better control over error handling logic.
class ProviderRequestError(RuntimeError):
    """Raised when an external AI/search provider request fails."""

# This exception is specifically for cases where Azure AI Search is configured but not yet ready to handle requests, allowing us to return a 503 Service Unavailable status code in the API response.
class SearchIndexNotReadyError(RuntimeError):
    """Raised when Azure AI Search is configured but not ready for use."""
