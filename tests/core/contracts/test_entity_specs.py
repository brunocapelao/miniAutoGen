"""Tests for SkillSpec, ToolSpec, McpServerBinding, EngineProfile, MemoryProfile."""

from __future__ import annotations

from miniautogen.core.contracts.engine_profile import EngineProfile
from miniautogen.core.contracts.mcp_binding import (
    McpExposeConfig,
    McpPolicy,
    McpServerBinding,
)
from miniautogen.core.contracts.memory_profile import MemoryProfile
from miniautogen.core.contracts.skill_spec import SkillActivation, SkillSpec
from miniautogen.core.contracts.tool_spec import (
    ToolExecution,
    ToolPolicy,
    ToolSpec,
)


class TestSkillSpec:
    """SkillSpec creation and defaults."""

    def test_minimal(self) -> None:
        spec = SkillSpec(id="code-review", name="Code Review")
        assert spec.id == "code-review"
        assert spec.version == "1.0.0"
        assert spec.description == ""
        assert spec.activation.keywords == []
        assert spec.tool_hints == {}
        assert spec.permissions == {}

    def test_full(self) -> None:
        spec = SkillSpec(
            id="testing",
            version="2.0.0",
            name="Testing Skill",
            description="Run and validate tests.",
            activation=SkillActivation(keywords=["test", "pytest"]),
            tool_hints={"testing": ["run_tests", "check_coverage"]},
            permissions={"shell": "sandbox"},
        )
        assert spec.activation.keywords == ["test", "pytest"]
        assert spec.tool_hints["testing"] == ["run_tests", "check_coverage"]

    def test_roundtrip(self) -> None:
        original = SkillSpec(id="s1", name="S1")
        restored = SkillSpec.model_validate(original.model_dump())
        assert restored == original


class TestToolSpec:
    """ToolSpec creation with execution target."""

    def test_minimal(self) -> None:
        spec = ToolSpec(name="web_search")
        assert spec.name == "web_search"
        assert spec.description == ""
        assert spec.input_schema == {}
        assert spec.execution.kind == "python"
        assert spec.execution.target == ""
        assert spec.policy.approval == "none"
        assert spec.policy.timeout_seconds == 30.0

    def test_with_execution_target(self) -> None:
        spec = ToolSpec(
            name="web_search",
            description="Search the web.",
            input_schema={"query": {"type": "string"}},
            execution=ToolExecution(
                kind="python",
                target="miniautogen.tools.web_search:execute",
            ),
            policy=ToolPolicy(approval="always", timeout_seconds=10.0),
        )
        assert spec.execution.target == "miniautogen.tools.web_search:execute"
        assert spec.policy.approval == "always"

    def test_mcp_kind(self) -> None:
        spec = ToolSpec(
            name="mcp_tool",
            execution=ToolExecution(kind="mcp", target="server:tool_name"),
        )
        assert spec.execution.kind == "mcp"

    def test_roundtrip(self) -> None:
        original = ToolSpec(
            name="t1",
            execution=ToolExecution(kind="http", target="https://api.example.com"),
        )
        restored = ToolSpec.model_validate(original.model_dump())
        assert restored == original


class TestMcpServerBinding:
    """McpServerBinding creation."""

    def test_minimal(self) -> None:
        binding = McpServerBinding(id="github")
        assert binding.id == "github"
        assert binding.transport == "stdio"
        assert binding.command is None
        assert binding.args == []
        assert binding.env == {}
        assert binding.expose.tools_mode == "allowlist"
        assert binding.expose.allow == []
        assert binding.policy.approval == "on_write"
        assert binding.policy.timeout_seconds == 60.0

    def test_full(self) -> None:
        binding = McpServerBinding(
            id="github",
            transport="sse",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "tok_xxx"},
            expose=McpExposeConfig(
                tools_mode="allowlist",
                allow=["create_issue", "list_prs"],
            ),
            policy=McpPolicy(approval="always", timeout_seconds=120.0),
        )
        assert binding.transport == "sse"
        assert binding.command == "npx"
        assert len(binding.args) == 2
        assert binding.env["GITHUB_TOKEN"] == "tok_xxx"
        assert binding.expose.allow == ["create_issue", "list_prs"]

    def test_roundtrip(self) -> None:
        original = McpServerBinding(id="m1", command="cmd")
        restored = McpServerBinding.model_validate(original.model_dump())
        assert restored == original


class TestEngineProfile:
    """EngineProfile with api and cli kinds."""

    def test_api_defaults(self) -> None:
        profile = EngineProfile()
        assert profile.kind == "api"
        assert profile.provider == "litellm"
        assert profile.model is None
        assert profile.command is None
        assert profile.temperature == 0.2

    def test_api_kind(self) -> None:
        profile = EngineProfile(
            kind="api",
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
        )
        assert profile.kind == "api"
        assert profile.provider == "openai"
        assert profile.model == "gpt-4o"
        assert profile.temperature == 0.7

    def test_cli_kind(self) -> None:
        profile = EngineProfile(
            kind="cli",
            provider="gemini",
            command="gemini",
        )
        assert profile.kind == "cli"
        assert profile.command == "gemini"

    def test_roundtrip(self) -> None:
        original = EngineProfile(kind="cli", provider="gemini", command="g")
        restored = EngineProfile.model_validate(original.model_dump())
        assert restored == original


class TestMemoryProfile:
    """MemoryProfile defaults."""

    def test_defaults(self) -> None:
        profile = MemoryProfile()
        assert profile.session is True
        assert profile.retrieval == {}
        assert profile.compaction == {}
        assert profile.summaries == {}
        assert profile.retention == {}

    def test_custom(self) -> None:
        profile = MemoryProfile(
            session=False,
            retrieval={"provider": "chroma", "top_k": 5},
            compaction={"strategy": "sliding_window", "max_tokens": 4000},
            summaries={"enabled": True},
            retention={"ttl_hours": 24},
        )
        assert profile.session is False
        assert profile.retrieval["provider"] == "chroma"
        assert profile.compaction["strategy"] == "sliding_window"

    def test_roundtrip(self) -> None:
        original = MemoryProfile(retrieval={"k": 10})
        restored = MemoryProfile.model_validate(original.model_dump())
        assert restored == original
