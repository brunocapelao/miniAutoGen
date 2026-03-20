"""Security tests for AgentSpec ID validation."""
import pytest
from miniautogen.core.contracts.agent_spec import AgentSpec


@pytest.mark.parametrize("malicious_id", [
    "../../etc/passwd",
    "../shared",
    "agent/../../root",
    "..",
    ".",
    "",
    "a" * 256,
    "agent name with spaces",
    "agent;rm -rf /",
])
def test_reject_malicious_agent_ids(malicious_id):
    with pytest.raises(ValueError):
        AgentSpec(id=malicious_id, name="Test")


@pytest.mark.parametrize("valid_id", [
    "architect",
    "claude-reviewer",
    "agent_1",
    "my.agent.v2",
    "A",
    "a" * 64,
])
def test_accept_valid_agent_ids(valid_id):
    spec = AgentSpec(id=valid_id, name="Test")
    assert spec.id == valid_id
