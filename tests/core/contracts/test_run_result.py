from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_result import RunResult


def test_run_result_exposes_terminal_status_and_run_id():
    result = RunResult(run_id="run-1", status="finished")

    assert result.run_id == "run-1"
    assert result.status == RunStatus.FINISHED
