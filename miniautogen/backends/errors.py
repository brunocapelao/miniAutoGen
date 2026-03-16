"""Error hierarchy for the backend driver layer.

All driver-related exceptions inherit from AgentDriverError so callers
can catch the whole category or specific subtypes.
"""


class AgentDriverError(Exception):
    """Base exception for all backend driver errors."""


class BackendUnavailableError(AgentDriverError):
    """The backend could not be reached or started."""


class SessionStartError(AgentDriverError):
    """Failed to start a session with the backend."""


class TurnExecutionError(AgentDriverError):
    """A turn failed during execution."""


class EventMappingError(AgentDriverError):
    """Failed to map a backend-native event to the canonical model."""


class CancelNotSupportedError(AgentDriverError):
    """The backend/driver does not support cancellation."""


class ArtifactCollectionError(AgentDriverError):
    """Failed to collect artifacts from the backend."""
