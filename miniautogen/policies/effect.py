"""Effect policy governing side-effect execution constraints.

Controls which effect types are allowed, per-step limits,
idempotency requirements, and stale-pending detection.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EffectPolicy(BaseModel):
    """Immutable policy for effect execution constraints.

    Consistent with other policies (ExecutionPolicy, RetryPolicy, etc.)
    using Pydantic BaseModel with frozen=True.

    Attributes:
        max_effects_per_step: Maximum side effects allowed per workflow step.
            Exceeding this raises EffectDeniedError.
        allowed_effect_types: Whitelist of permitted effect types.
            None means all types are allowed.
        require_idempotency: Whether all effects must go through
            EffectInterceptor for deduplication.
        stale_pending_timeout_seconds: Time after which a PENDING record
            is considered stale (crashed executor). Must be >= 2x the
            maximum expected tool execution time. When reclaimed, emits
            EFFECT_STALE_RECLAIMED event.
    """

    model_config = ConfigDict(frozen=True)

    max_effects_per_step: int = 10
    allowed_effect_types: frozenset[str] | None = None
    require_idempotency: bool = True
    stale_pending_timeout_seconds: float = 3600.0
