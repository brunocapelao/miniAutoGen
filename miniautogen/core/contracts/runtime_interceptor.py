"""RuntimeInterceptor protocol for composable step-level middleware.

Defines 4 hooks that participate in flow execution:
- before_step (Waterfall): transforms input, called in series
- should_execute (Bail): decides if step runs, any False = skip
- after_step (Series): transforms result, called in series
- on_error: handles step failure

Interceptors are composable, stateless, and order-dependent.
The order of registration determines the order of execution.

See docs/pt/architecture/04-fluxos.md Fluxo 9 and DA-11.
See docs/pt/architecture/05-invariantes.md RuntimeInterceptor invariants.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from miniautogen.core.contracts.run_context import RunContext


@runtime_checkable
class RuntimeInterceptor(Protocol):
    """Composable middleware for step-level interception in flows.

    All methods are async (AnyIO invariant). Interceptors MUST NOT
    rewrite domain semantics -- they observe and transform, not
    replace coordination logic.
    """

    async def before_step(
        self,
        input: Any,
        context: RunContext,
    ) -> Any:
        """Transform input before step execution (Waterfall semantics).

        Each interceptor receives the output of the previous one.
        Return input unmodified for pass-through.
        """
        ...

    async def should_execute(
        self,
        context: RunContext,
    ) -> bool:
        """Decide if the step should execute (Bail semantics).

        If any interceptor returns False, the step is unconditionally
        skipped. There is no override mechanism -- bail is deterministic.
        """
        ...

    async def after_step(
        self,
        result: Any,
        context: RunContext,
    ) -> Any:
        """Transform result after step execution (Series semantics).

        Each interceptor processes the result in registration order.
        Return result unmodified for pass-through.
        """
        ...

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> Any:
        """Handle step failure.

        Return a fallback value to recover, or None to propagate
        the error.
        """
        ...
