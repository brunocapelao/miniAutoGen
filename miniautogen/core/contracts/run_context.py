from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_serializer

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class FrozenState(MiniAutoGenBaseModel):
    """Typed, immutable state container replacing execution_state.

    Stores arbitrary key-value pairs as a tuple of pairs,
    ensuring no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    _data: tuple[tuple[str, Any], ...] = ()

    def __init__(self, **kwargs: Any) -> None:
        pairs = tuple(sorted(kwargs.items()))
        super().__init__()
        object.__setattr__(self, '_data', pairs)

    def get(self, key: str, default: Any = None) -> Any:
        """Look up a key, returning default if not found."""
        for k, v in self._data:
            if k == key:
                return v
        return default

    def evolve(self, **updates: Any) -> "FrozenState":
        """Return a new FrozenState with the given updates applied."""
        current = dict(self._data)
        current.update(updates)
        return FrozenState(**current)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict copy of the state."""
        return dict(self._data)

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize as a plain dict for Pydantic model_dump()."""
        return dict(self._data)


class RunContext(MiniAutoGenBaseModel):
    """Typed, frozen execution context for a single framework run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    correlation_id: str
    state: FrozenState = FrozenState()
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    def with_state(self, **updates: Any) -> "RunContext":
        """Return a new RunContext with state evolved by the given updates."""
        new_state = self.state.evolve(**updates)
        return self.model_copy(update={"state": new_state})

    def with_previous_result(self, result: Any) -> "RunContext":
        """Return a new RunContext with the previous result injected.

        The previous result is set as ``input_payload`` and a reference
        is stored in ``metadata`` for traceability.
        """
        new_metadata = dict(self.metadata)
        new_metadata["previous_result"] = result
        return self.model_copy(
            update={
                "input_payload": result,
                "metadata": tuple(sorted(new_metadata.items())),
            },
        )

    def evolve_metadata(self, **updates: Any) -> "RunContext":
        """Return a new RunContext with metadata evolved by the given updates."""
        current = dict(self.metadata)
        current.update(updates)
        return self.model_copy(
            update={"metadata": tuple(sorted(current.items()))},
        )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Look up a metadata key without exposing the internal tuple."""
        for k, v in self.metadata:
            if k == key:
                return v
        return default
