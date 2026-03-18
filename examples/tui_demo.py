"""Demo script to test MiniAutoGen Dash TUI with simulated events.

Run with: poetry run python examples/tui_demo.py
"""

from __future__ import annotations

import asyncio
import random

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.tui import MiniAutoGenDash, TuiEventSink


async def simulate_pipeline(sink: TuiEventSink) -> None:
    """Simulate a multi-agent pipeline execution with realistic events."""
    run_id = "run-demo-001"
    agents = [
        ("planner", "Planner", "Architect"),
        ("writer", "Writer", "Developer"),
        ("reviewer", "Reviewer", "QA Lead"),
        ("editor", "Editor", "Refiner"),
    ]

    # Wait for app to be ready
    await asyncio.sleep(1)

    # RUN_STARTED
    await sink.publish(ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        run_id=run_id,
        scope="pipeline_runner",
        payload={"pipeline_name": "main", "agent_count": len(agents)},
    ))
    await asyncio.sleep(0.5)

    for i, (agent_id, name, role) in enumerate(agents):
        step_num = i + 1

        # COMPONENT_STARTED
        await sink.publish(ExecutionEvent(
            type=EventType.COMPONENT_STARTED.value,
            run_id=run_id,
            scope=f"step_{step_num}",
            payload={
                "agent_id": agent_id,
                "agent_name": name,
                "agent_role": role,
                "step": step_num,
                "total_steps": len(agents),
            },
        ))
        await asyncio.sleep(0.3)

        # Simulate agent thinking (BACKEND_TURN_STARTED)
        await sink.publish(ExecutionEvent(
            type=EventType.BACKEND_TURN_STARTED.value,
            run_id=run_id,
            scope=agent_id,
            payload={"agent_id": agent_id, "model": "gpt-4o"},
        ))
        await asyncio.sleep(random.uniform(1.0, 2.5))

        # AGENT_REPLIED
        replies = {
            "planner": "I recommend a 3-layer architecture: AuthProvider protocol, JWTAdapter, and AuthMiddleware.",
            "writer": "Implementing the AuthProvider protocol with async authenticate() method...\n\n```python\nclass AuthProvider(Protocol):\n    async def authenticate(self, creds: Credentials) -> AuthResult: ...\n```",
            "reviewer": "Code review passed. The protocol correctly isolates the auth concern. One suggestion: add a refresh_token() method.",
            "editor": "Applied reviewer suggestions. Added refresh_token() and updated docstrings for clarity.",
        }
        await sink.publish(ExecutionEvent(
            type=EventType.AGENT_REPLIED.value,
            run_id=run_id,
            scope=agent_id,
            payload={
                "agent_id": agent_id,
                "content": replies[agent_id],
                "tokens": random.randint(200, 1200),
            },
        ))
        await asyncio.sleep(0.3)

        # Simulate tool usage for some agents
        if agent_id in ("planner", "writer"):
            tool_name = "file_read" if agent_id == "planner" else "code_gen"
            await sink.publish(ExecutionEvent(
                type=EventType.TOOL_INVOKED.value,
                run_id=run_id,
                scope=agent_id,
                payload={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "action": "read src/core/contracts/" if agent_id == "planner" else "write src/auth.py",
                },
            ))
            await asyncio.sleep(0.8)

            await sink.publish(ExecutionEvent(
                type=EventType.TOOL_SUCCEEDED.value,
                run_id=run_id,
                scope=agent_id,
                payload={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "result": "42 lines read" if agent_id == "planner" else "34 lines written",
                },
            ))
            await asyncio.sleep(0.3)

        # Simulate HITL approval for the writer
        if agent_id == "writer":
            await sink.publish(ExecutionEvent(
                type=EventType.APPROVAL_REQUESTED.value,
                run_id=run_id,
                scope=agent_id,
                payload={
                    "agent_id": agent_id,
                    "action": "deploy auth module to staging",
                    "description": "Writer wants to deploy the auth module",
                    "files": ["auth.py", "middleware.py", "config.py"],
                },
            ))
            # Wait a bit for the user to see the approval
            await asyncio.sleep(3)

            await sink.publish(ExecutionEvent(
                type=EventType.APPROVAL_GRANTED.value,
                run_id=run_id,
                scope=agent_id,
                payload={"agent_id": agent_id, "action": "deploy auth module"},
            ))
            await asyncio.sleep(0.5)

        # CHECKPOINT_SAVED
        await sink.publish(ExecutionEvent(
            type=EventType.CHECKPOINT_SAVED.value,
            run_id=run_id,
            scope=f"step_{step_num}",
            payload={"checkpoint_id": f"cp-{step_num}", "step": step_num},
        ))
        await asyncio.sleep(0.2)

        # COMPONENT_FINISHED
        await sink.publish(ExecutionEvent(
            type=EventType.COMPONENT_FINISHED.value,
            run_id=run_id,
            scope=f"step_{step_num}",
            payload={
                "agent_id": agent_id,
                "step": step_num,
                "total_steps": len(agents),
            },
        ))
        await asyncio.sleep(0.5)

    # RUN_FINISHED
    await sink.publish(ExecutionEvent(
        type=EventType.RUN_FINISHED.value,
        run_id=run_id,
        scope="pipeline_runner",
        payload={"pipeline_name": "main", "status": "completed"},
    ))


def main() -> None:
    """Launch the TUI with simulated pipeline events."""
    sink = TuiEventSink()
    app = MiniAutoGenDash()

    # Store sink on app so widgets can access it
    app._event_sink = sink  # type: ignore[attr-defined]

    async def run_with_simulation() -> None:
        # Run simulation in background
        async with asyncio.TaskGroup() as tg:
            tg.create_task(simulate_pipeline(sink))
            # The app.run_async() would block, so we just run the sim
            # For a real integration, the PipelineRunner feeds the sink

    # For now, just launch the app standalone
    print("Launching MiniAutoGen Dash...")
    print("Press 'q' to quit, '?' for help, ':' for command palette")
    print()
    app.run()


if __name__ == "__main__":
    main()
