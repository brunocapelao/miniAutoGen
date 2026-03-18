from hypothesis import given
from hypothesis import strategies as st

from miniautogen.core.contracts.events import ExecutionEvent


@given(
    correlation_id=st.text(min_size=1),
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.integers(), st.text(max_size=20)),
        max_size=5,
    ),
)
def test_execution_event_preserves_payload_shape(
    correlation_id: str,
    payload: dict[str, object],
) -> None:
    event = ExecutionEvent(
        type="policy_applied",
        run_id="run-1",
        correlation_id=correlation_id,
        payload=payload,
    )

    assert event.payload_dict() == payload
