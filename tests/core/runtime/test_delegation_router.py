import pytest
from miniautogen.core.contracts.delegation import DelegationRouterProtocol
from miniautogen.core.runtime.delegation_router import ConfigDelegationRouter
from miniautogen.core.runtime.agent_errors import (
    DelegationDepthExceededError, AgentSecurityError,
)


def test_implements_protocol():
    router = ConfigDelegationRouter(configs={})
    assert isinstance(router, DelegationRouterProtocol)


def test_can_delegate_allowed():
    configs = {
        "architect": {"can_delegate_to": ["developer"], "max_depth": 2},
        "developer": {"can_delegate_to": [], "max_depth": 1},
    }
    router = ConfigDelegationRouter(configs=configs)
    assert router.can_delegate("architect", "developer")


def test_can_delegate_denied():
    configs = {
        "architect": {"can_delegate_to": ["developer"], "max_depth": 2},
        "developer": {"can_delegate_to": [], "max_depth": 1},
    }
    router = ConfigDelegationRouter(configs=configs)
    assert not router.can_delegate("developer", "architect")
    assert not router.can_delegate("architect", "unknown")


def test_can_delegate_unknown_source():
    router = ConfigDelegationRouter(configs={})
    assert not router.can_delegate("unknown", "anyone")


@pytest.mark.anyio
async def test_delegate_unauthorized_raises():
    configs = {"a": {"can_delegate_to": [], "max_depth": 1}}
    router = ConfigDelegationRouter(configs=configs)
    with pytest.raises(AgentSecurityError, match="not allowed"):
        await router.delegate("a", "b", "input")


@pytest.mark.anyio
async def test_delegate_depth_exceeded_raises():
    configs = {"a": {"can_delegate_to": ["b"], "max_depth": 1}}
    router = ConfigDelegationRouter(configs=configs)

    # Register a mock target
    class MockAgent:
        async def process(self, input):
            return f"processed: {input}"

    router.register_agent("b", MockAgent())

    with pytest.raises(DelegationDepthExceededError):
        await router.delegate("a", "b", "input", current_depth=1)


@pytest.mark.anyio
async def test_delegate_success():
    configs = {"a": {"can_delegate_to": ["b"], "max_depth": 2}}
    router = ConfigDelegationRouter(configs=configs)

    class MockAgent:
        async def process(self, input):
            return f"result: {input}"

    router.register_agent("b", MockAgent())

    result = await router.delegate("a", "b", "hello", current_depth=0)
    assert result == "result: hello"


@pytest.mark.anyio
async def test_delegate_target_not_found():
    configs = {"a": {"can_delegate_to": ["b"], "max_depth": 2}}
    router = ConfigDelegationRouter(configs=configs)
    with pytest.raises(AgentSecurityError, match="not found"):
        await router.delegate("a", "b", "input")
