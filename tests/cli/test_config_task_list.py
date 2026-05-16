"""Tests for TaskListConfig parsing, validation, and cycle detection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from miniautogen.cli.config import FlowConfig, _has_cycle
from miniautogen.core.contracts.team_task import TaskEntrySpec, TaskListConfig


def test_task_entry_spec_defaults() -> None:
    spec = TaskEntrySpec(title="Test")
    assert spec.title == "Test"
    assert spec.description is None
    assert spec.assigned_to is None
    assert spec.labels == []
    assert spec.depends_on == []
    assert spec.id is None


def test_task_list_config_defaults() -> None:
    cfg = TaskListConfig()
    assert cfg.enabled is False
    assert cfg.initial_tasks == []
    assert cfg.idle_threshold_seconds == 5.0
    assert cfg.poll_interval_ms == 200


def test_flow_config_with_task_list() -> None:
    flow = FlowConfig(
        mode="team",
        participants=["legal", "security"],
        lead="orchestrator",
        task_list=TaskListConfig(
            enabled=True,
            initial_tasks=[
                TaskEntrySpec(title="Review contract", assigned_to="legal"),
                TaskEntrySpec(title="Security audit", assigned_to="security"),
            ],
        ),
    )
    assert flow.task_list is not None
    assert flow.task_list.enabled is True
    assert len(flow.task_list.initial_tasks) == 2


def test_valid_dag_passes() -> None:
    specs = [
        TaskEntrySpec(title="A", id="a"),
        TaskEntrySpec(title="B", id="b", depends_on=["a"]),
        TaskEntrySpec(title="C", id="c", depends_on=["b"]),
    ]
    assert _has_cycle(specs) is False


def test_cycle_detected() -> None:
    specs = [
        TaskEntrySpec(title="A", id="a", depends_on=["c"]),
        TaskEntrySpec(title="B", id="b", depends_on=["a"]),
        TaskEntrySpec(title="C", id="c", depends_on=["b"]),
    ]
    assert _has_cycle(specs) is True


def test_empty_dag_no_cycle() -> None:
    assert _has_cycle([]) is False


def test_self_reference_is_cycle() -> None:
    specs = [
        TaskEntrySpec(title="A", id="a", depends_on=["a"]),
    ]
    assert _has_cycle(specs) is True


def test_flow_config_rejects_cycle() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        FlowConfig(
            mode="team",
            participants=["legal"],
            lead="orchestrator",
            task_list=TaskListConfig(
                enabled=True,
                initial_tasks=[
                    TaskEntrySpec(title="A", id="a", depends_on=["b"]),
                    TaskEntrySpec(title="B", id="b", depends_on=["a"]),
                ],
            ),
        )


def test_yaml_parse_with_task_list(tmp_path: pytest.TempPathFactory) -> None:
    from pathlib import Path

    from miniautogen.cli.config import WorkspaceConfig

    yaml_content = """
project:
  name: test-project
defaults:
  engine: test
flows:
  review_team:
    mode: team
    lead: orchestrator
    participants:
      - legal
      - security
    task_list:
      enabled: true
      initial_tasks:
        - title: "Review contract"
          assigned_to: legal
        - title: "Security audit"
          assigned_to: security
          depends_on:
            - "task[0]"
"""
    config_path = Path(tmp_path) / "miniautogen.yaml"
    config_path.write_text(yaml_content)

    raw = __import__("yaml").safe_load(yaml_content)
    config = WorkspaceConfig.model_validate(raw)
    flow = config.flows["review_team"]
    assert flow.task_list is not None
    assert flow.task_list.enabled is True
    assert len(flow.task_list.initial_tasks) == 2
