from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import RunContext


def test_run_context_requires_core_operational_fields():
    ctx = RunContext(
        run_id="run-1",
        started_at=datetime.now(UTC),
        correlation_id="corr-1",
        execution_state={},
        input_payload={"message": "hello"},
    )

    assert ctx.run_id == "run-1"
    assert ctx.correlation_id == "corr-1"


def test_run_context_rejects_missing_run_id():
    with pytest.raises(ValidationError):
        RunContext(
            started_at=datetime.now(UTC),
            correlation_id="corr-1",
            execution_state={},
            input_payload={},
        )
