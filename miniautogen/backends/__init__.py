"""Unified driver abstraction for external agent backends.

Usage::

    from miniautogen.backends import AgentDriver, BackendResolver, BackendConfig
"""

from miniautogen.backends.agentapi import AgentAPIDriver, agentapi_factory
from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.backends.resolver import BackendResolver
from miniautogen.backends.sessions import SessionManager

__all__ = [
    "AgentAPIDriver",
    "AgentDriver",
    "AgentEvent",
    "ArtifactRef",
    "BackendCapabilities",
    "BackendConfig",
    "BackendResolver",
    "CancelTurnRequest",
    "DriverType",
    "SendTurnRequest",
    "SessionManager",
    "StartSessionRequest",
    "StartSessionResponse",
    "agentapi_factory",
]
