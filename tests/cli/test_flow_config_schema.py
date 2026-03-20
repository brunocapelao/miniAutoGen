"""Tests for the extended FlowConfig schema (Task 4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from miniautogen.cli.config import FlowConfig, PipelineConfig


class TestFlowConfigTargetOnly:
    def test_target_only_is_valid(self):
        cfg = FlowConfig(target="mymodule:run")
        assert cfg.target == "mymodule:run"
        assert cfg.mode is None
        assert cfg.participants == []

    def test_target_with_extra_fields_is_valid(self):
        cfg = FlowConfig(target="mymodule:run", max_rounds=5)
        assert cfg.max_rounds == 5

    def test_target_with_mode_no_participants_is_valid(self):
        """When target is also set, participants are not required."""
        cfg = FlowConfig(target="mymodule:run", mode="workflow")
        assert cfg.target == "mymodule:run"
        assert cfg.mode == "workflow"
        assert cfg.participants == []


class TestFlowConfigModeParticipants:
    def test_mode_with_participants_is_valid(self):
        cfg = FlowConfig(mode="workflow", participants=["alice", "bob"])
        assert cfg.mode == "workflow"
        assert cfg.participants == ["alice", "bob"]

    def test_defaults_are_applied(self):
        cfg = FlowConfig(mode="workflow", participants=["alice"])
        assert cfg.max_rounds == 3
        assert cfg.max_turns == 20
        assert cfg.chain_flows == []
        assert cfg.input_text is None
        assert cfg.leader is None
        assert cfg.router is None


class TestFlowConfigValidationErrors:
    def test_neither_target_nor_mode_raises(self):
        with pytest.raises(ValidationError, match="either 'target' or 'mode'"):
            FlowConfig()

    def test_mode_without_participants_raises(self):
        """Pure config-driven mode (no target) requires participants."""
        with pytest.raises(ValidationError, match="requires 'participants'"):
            FlowConfig(mode="workflow", participants=[])

    def test_deliberation_without_leader_raises(self):
        """Pure config-driven deliberation requires leader."""
        with pytest.raises(ValidationError, match="requires 'leader'"):
            FlowConfig(mode="deliberation", participants=["alice", "bob"])

    def test_deliberation_with_leader_is_valid(self):
        cfg = FlowConfig(
            mode="deliberation",
            participants=["alice", "bob"],
            leader="alice",
        )
        assert cfg.leader == "alice"

    def test_deliberation_with_target_no_leader_is_valid(self):
        """When target is set, deliberation leader is not required."""
        cfg = FlowConfig(
            target="mymodule:run",
            mode="deliberation",
        )
        assert cfg.leader is None

    def test_loop_without_router_raises(self):
        """Pure config-driven loop requires router."""
        with pytest.raises(ValidationError, match="requires 'router'"):
            FlowConfig(mode="loop", participants=["alice"])

    def test_loop_with_router_is_valid(self):
        cfg = FlowConfig(
            mode="loop",
            participants=["alice"],
            router="mymodule:router_fn",
        )
        assert cfg.router == "mymodule:router_fn"

    def test_loop_with_target_no_router_is_valid(self):
        """When target is set, loop router is not required."""
        cfg = FlowConfig(target="mymodule:run", mode="loop")
        assert cfg.router is None


class TestFlowConfigBackwardCompat:
    def test_pipeline_config_is_alias_for_flow_config(self):
        assert PipelineConfig is FlowConfig

    def test_pipeline_config_target_only(self):
        cfg = PipelineConfig(target="legacy:target")
        assert cfg.target == "legacy:target"

    def test_pipeline_config_invalid_raises(self):
        with pytest.raises(ValidationError):
            PipelineConfig()
