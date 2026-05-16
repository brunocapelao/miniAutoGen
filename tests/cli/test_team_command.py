"""Tests for the CLI team command with experimental gate.

Spec 015 requires MINIAUTOGEN_EXPERIMENTAL_TEAMS=1 to enable team runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import FlowConfig


def test_experimental_gate_required(tmp_path: Path) -> None:
    """Without env var, team mode must raise usage error."""
    config_path = tmp_path / "miniautogen.yaml"
    config_data = {
        "project": {"name": "test"},
        "flows": {
            "review_team": {
                "mode": "team",
                "participants": ["orchestrator", "legal"],
                "lead": "orchestrator",
            },
        },
    }
    with config_path.open("w") as f:
        yaml.dump(config_data, f)

    from miniautogen.cli.config import load_config

    config = load_config(config_path)
    flow = config.pipelines["review_team"]
    assert flow.mode == "team"


def test_flow_config_team_mode_validation() -> None:
    """FlowConfig must accept team mode with valid lead and teammates."""
    config = FlowConfig(
        mode="team",
        lead="orchestrator",
        participants=["orchestrator", "legal", "security"],
    )
    assert config.mode == "team"
    assert config.lead == "orchestrator"
    assert len(config.participants) == 3


def test_flow_config_team_missing_lead_raises() -> None:
    """Team mode must require participants."""
    with pytest.raises(ValueError, match="requires 'participants'"):
        FlowConfig(
            mode="team",
            participants=[],
        )
