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
    """Typed execution context for a single framework run."""

    run_id: str
    started_at: datetime
    correlation_id: str
    execution_state: dict[str, Any] = Field(default_factory=dict)
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def with_previous_result(self, result: Any) -> "RunContext":
        """Create a new RunContext with the previous result injected.

        The previous result is set as ``input_payload`` and a reference
        is stored in ``metadata["previous_result"]`` for traceability.
        """
        new_metadata = {**self.metadata, "previous_result": result}
        return self.model_copy(
            update={"input_payload": result, "metadata": new_metadata},
        )
