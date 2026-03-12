from miniautogen.core.contracts.run_result import RunResult


def test_run_result_exposes_terminal_status_and_run_id():
    result = RunResult(run_id="run-1", status="succeeded")

    assert result.run_id == "run-1"
    assert result.status == "succeeded"
