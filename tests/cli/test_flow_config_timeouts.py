"""Tests for FlowConfig timeout fields — Spec 013."""

import warnings

import pytest
from pydantic import ValidationError

from miniautogen.cli.config import FlowConfig


class TestFlowConfigTimeouts:
    def test_no_timeout_fields_is_valid(self) -> None:
        """YAML without agent_timeouts/round_timeouts validates."""
        config = FlowConfig(
            mode="deliberation",
            participants=["advogado", "engenheiro"],
            leader="advogado",
        )
        assert config.agent_timeouts == {}
        assert config.round_timeouts == {}
        assert config.on_timeout_action == "continue"

    def test_agent_timeouts_dict_accepted(self) -> None:
        """dict of {'engenheiro': 60.0} is accepted."""
        config = FlowConfig(
            mode="deliberation",
            participants=["advogado", "engenheiro"],
            leader="advogado",
            agent_timeouts={"engenheiro": 60.0},
        )
        assert config.agent_timeouts["engenheiro"] == 60.0

    def test_timeout_below_one_second_rejected(self) -> None:
        """Values < 1.0 raise ValidationError."""
        with pytest.raises(ValidationError):
            FlowConfig(
                mode="deliberation",
                participants=["advogado"],
                leader="advogado",
                agent_timeouts={"advogado": 0.5},
            )

    def test_on_timeout_action_invalid_rejected(self) -> None:
        """Invalid on_timeout_action raises error."""
        with pytest.raises(ValidationError):
            FlowConfig(
                mode="deliberation",
                participants=["advogado"],
                leader="advogado",
                on_timeout_action="foo",
            )

    def test_unknown_agent_id_in_timeouts_warns(self) -> None:
        """Unknown agent IDs emit a warning (not a fatal error)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FlowConfig(
                mode="deliberation",
                participants=["advogado", "engenheiro"],
                leader="advogado",
                agent_timeouts={"advogado": 120.0, "unknown_agent": 60.0},
            )
            unknown_warnings = [
                x.message for x in w if "unknown_agent" in str(x.message)
            ]
            assert len(unknown_warnings) >= 1
