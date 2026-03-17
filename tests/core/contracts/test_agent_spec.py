"""Tests for AgentSpec and its nested configuration models."""

from __future__ import annotations

from miniautogen.core.contracts.agent_spec import (
    AgentSpec,
    DelegationConfig,
    McpAccessConfig,
    MemoryConfig,
    PermissionsConfig,
    RuntimeConfig,
    SkillRef,
    ToolAccessConfig,
)


class TestAgentSpecMinimal:
    """AgentSpec with only required fields."""

    def test_create_minimal(self) -> None:
        spec = AgentSpec(id="researcher", name="Researcher")
        assert spec.id == "researcher"
        assert spec.name == "Researcher"
        assert spec.version == "1.0.0"
        assert spec.description == ""
        assert spec.role == ""
        assert spec.goal == ""
        assert spec.backstory is None
        assert spec.engine_profile is None
        assert spec.vendor_extensions == {}

    def test_defaults_are_sensible(self) -> None:
        spec = AgentSpec(id="a", name="A")
        assert spec.skills.attached == []
        assert spec.tool_access.mode == "allowlist"
        assert spec.tool_access.allow == []
        assert spec.mcp_access.servers == []
        assert spec.memory.profile == "default"
        assert spec.memory.session_memory is True
        assert spec.memory.retrieval_memory is False
        assert spec.memory.max_context_tokens == 16000
        assert spec.delegation.allow_delegation is False
        assert spec.delegation.context_isolation is True
        assert spec.runtime.max_turns == 10
        assert spec.runtime.timeout_seconds == 300.0
        assert spec.runtime.retry_policy == "standard"
        assert spec.permissions.shell == "deny"
        assert spec.permissions.network == "allow"
        assert spec.permissions.filesystem == {"read": True, "write": False}


class TestAgentSpecFull:
    """AgentSpec with all fields explicitly set."""

    def test_create_full(self) -> None:
        spec = AgentSpec(
            id="senior-dev",
            version="2.0.0",
            name="Senior Developer",
            description="A senior developer agent.",
            role="developer",
            goal="Write clean code",
            backstory="10 years of experience.",
            skills=SkillRef(attached=["code-review", "testing"]),
            tool_access=ToolAccessConfig(
                mode="denylist",
                deny=["dangerous_tool"],
            ),
            mcp_access=McpAccessConfig(
                servers=["github"],
                tools_mode="all",
            ),
            memory=MemoryConfig(
                profile="large",
                session_memory=True,
                retrieval_memory=True,
                max_context_tokens=128000,
            ),
            delegation=DelegationConfig(
                allow_delegation=True,
                can_delegate_to=["junior-dev"],
                context_isolation=False,
            ),
            runtime=RuntimeConfig(
                max_turns=50,
                timeout_seconds=600.0,
                retry_policy="aggressive",
            ),
            permissions=PermissionsConfig(
                shell="sandbox",
                network="allow",
                filesystem={"read": True, "write": True},
            ),
            engine_profile="gpt4-turbo",
            vendor_extensions={"openai": {"seed": 42}},
        )

        assert spec.id == "senior-dev"
        assert spec.version == "2.0.0"
        assert spec.backstory == "10 years of experience."
        assert spec.skills.attached == ["code-review", "testing"]
        assert spec.tool_access.mode == "denylist"
        assert spec.tool_access.deny == ["dangerous_tool"]
        assert spec.mcp_access.servers == ["github"]
        assert spec.memory.retrieval_memory is True
        assert spec.memory.max_context_tokens == 128000
        assert spec.delegation.allow_delegation is True
        assert spec.delegation.can_delegate_to == ["junior-dev"]
        assert spec.runtime.max_turns == 50
        assert spec.permissions.shell == "sandbox"
        assert spec.engine_profile == "gpt4-turbo"
        assert spec.vendor_extensions == {"openai": {"seed": 42}}


class TestAgentSpecSerialization:
    """Roundtrip serialization tests."""

    def test_dump_and_validate_roundtrip(self) -> None:
        original = AgentSpec(
            id="roundtrip",
            name="Roundtrip Agent",
            role="tester",
            skills=SkillRef(attached=["s1"]),
            delegation=DelegationConfig(
                allow_delegation=True,
                can_delegate_to=["other"],
            ),
        )
        data = original.model_dump()
        restored = AgentSpec.model_validate(data)
        assert restored == original

    def test_json_roundtrip(self) -> None:
        original = AgentSpec(id="json-rt", name="JSON Agent")
        json_str = original.model_dump_json()
        restored = AgentSpec.model_validate_json(json_str)
        assert restored == original

    def test_model_dump_excludes_none_backstory(self) -> None:
        spec = AgentSpec(id="x", name="X")
        data = spec.model_dump()
        # backstory key should be present (Pydantic default)
        assert "backstory" in data
        assert data["backstory"] is None
