"""Tests for AgentFilesystemSandbox and ToolExecutionPolicy."""
import pytest
from pathlib import Path
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox, ToolExecutionPolicy


def test_can_read_own_config(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    config_path = workspace / ".miniautogen" / "agents" / "architect" / "tools.yml"
    assert sandbox.can_read(config_path)


def test_cannot_read_other_agent_config(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    other_path = workspace / ".miniautogen" / "agents" / "developer" / "memory" / "context.json"
    assert not sandbox.can_read(other_path)


def test_can_read_workspace_source(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    src_path = workspace / "src" / "main.py"
    assert sandbox.can_read(src_path)


def test_can_read_shared(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    shared_path = workspace / ".miniautogen" / "shared" / "memory" / "data.json"
    assert sandbox.can_read(shared_path)


def test_cannot_write_prompt_md(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    prompt_path = workspace / ".miniautogen" / "agents" / "architect" / "prompt.md"
    assert not sandbox.can_write(prompt_path)


def test_can_write_own_memory(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    sandbox = AgentFilesystemSandbox("architect", workspace)
    memory_path = workspace / ".miniautogen" / "agents" / "architect" / "memory" / "entry.json"
    assert sandbox.can_write(memory_path)


def test_tool_execution_policy_defaults():
    policy = ToolExecutionPolicy()
    assert policy.timeout_per_tool == 30.0
    assert policy.max_concurrent_tools == 5
    assert policy.max_tool_calls_per_turn == 20
    assert policy.max_cumulative_tool_time == 120.0
