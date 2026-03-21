#!/usr/bin/env python3
"""MiniAutoGen E2E Demo: AI Dev Team Builds a Terminal Tamagotchi.

Uses the REAL MiniAutoGen SDK:
- PipelineRunner.run_from_config() for orchestration
- WorkflowRuntime for sequential build pipeline
- DeliberationRuntime for peer code review
- CLIAgentDriver (via EngineResolver) for Gemini CLI backend
- InMemoryEventSink for observability
- Events emitted automatically by the runtimes

Four agents (Architect, Developer, Tester, Tech Lead) collaborate
through Workflow and Deliberation coordination modes to build a
terminal Tamagotchi game.
"""

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

# ── MiniAutoGen SDK ──────────────────────────────────────────────
from miniautogen.cli.config import load_config
from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner

# ── Configuration ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
WORKSPACE = PROJECT_ROOT / "workspace"
MAX_ITERATIONS = 3


def banner(text: str, char: str = "=", width: int = 60) -> None:
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


async def main() -> None:
    # ── Pre-flight checks ────────────────────────────────────────
    if not shutil.which("gemini"):
        print("ERROR: 'gemini' CLI not found in PATH.")
        print("Install: https://github.com/google-gemini/gemini-cli")
        sys.exit(1)

    WORKSPACE.mkdir(exist_ok=True)

    # ── Load project config and agent specs (from YAML) ──────────
    config = load_config(PROJECT_ROOT / "miniautogen.yaml")
    agent_specs = load_agent_specs(PROJECT_ROOT)

    banner("MiniAutoGen E2E Demo: AI Dev Team Builds a Tamagotchi")
    print(f"  Agents: {', '.join(agent_specs.keys())}")
    print(f"  Engine: {config.defaults.engine}")
    print(f"  Max iterations: {MAX_ITERATIONS}")
    print(f"  Workspace: {WORKSPACE}")

    # ── Create SDK primitives ────────────────────────────────────
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)

    # ── Get flow configs from project YAML ───────────────────────
    build_flow = config.flows["build"]      # mode: workflow
    review_flow = config.flows["review"]    # mode: deliberation

    start_time = time.time()
    verdict = "NEEDS_WORK"
    feedback = ""

    # ── Outer loop: iterate until Tech Lead approves ─────────────
    for iteration in range(1, MAX_ITERATIONS + 1):
        banner(f"ITERATION {iteration}/{MAX_ITERATIONS}", char="*")

        # ── Phase 1: Build (Workflow Mode) ───────────────────────
        # PipelineRunner orchestrates: Architect → Developer → Tester
        # Each agent gets the previous agent's output as input.
        # The CLIAgentDriver calls `gemini --yolo -p <prompt>` internally.
        # Events (RUN_STARTED, COMPONENT_STARTED, AGENT_REPLIED, etc.)
        # are emitted AUTOMATICALLY by the runtimes.
        banner(f"PHASE 1: BUILD (Workflow Mode) — Iteration {iteration}")

        build_input = (
            "Build a terminal Tamagotchi game in Python.\n\n"
            "Requirements:\n"
            "- A pet with stats: hunger, happiness, energy (0-100, start at 50)\n"
            "- Actions: feed (+20 hunger), play (+20 happiness, -10 energy), "
            "sleep (+30 energy, -10 hunger)\n"
            "- Stats decay by 5 each turn\n"
            "- Game over when any stat hits 0\n"
            "- ASCII art for pet states\n"
            "- Turn-based loop: show status → choose action → update stats\n"
            "- Single file: tamagotchi.py, runnable with `python tamagotchi.py`\n"
        )
        if feedback:
            build_input += f"\nTech Lead feedback from previous iteration:\n{feedback}\n"

        print("  Running Workflow: Architect → Developer → Tester")
        build_result = await runner.run_from_config(
            flow_config=build_flow,
            agent_specs=agent_specs,
            workspace=WORKSPACE,
            config=config,
            input_text=build_input,
        )
        print(f"  Build complete. Result status: {build_result.status}")

        # ── Phase 2: Review (Deliberation Mode) ─────────────────
        # PipelineRunner orchestrates deliberation: each agent reviews
        # from their perspective, then the leader (Architect) consolidates.
        banner(f"PHASE 2: REVIEW (Deliberation Mode) — Iteration {iteration}")

        review_input = (
            "Review the current Tamagotchi implementation in the workspace.\n"
            "Check code quality, test coverage, and design clarity.\n"
            "Each reviewer provides their perspective, then the leader consolidates."
        )

        print("  Running Deliberation: Architect + Developer + Tester review")
        review_result = await runner.run_from_config(
            flow_config=review_flow,
            agent_specs=agent_specs,
            workspace=WORKSPACE,
            config=config,
            input_text=review_input,
        )
        review_report = str(review_result.output) if review_result.output else "No report"
        print(f"  Review complete. Result status: {review_result.status}")

        # ── Phase 3: Tech Lead Decision ──────────────────────────
        # Single agent call — Tech Lead evaluates and returns verdict.
        # We use a minimal workflow with just the tech_lead agent.
        banner(f"PHASE 3: DECISION (Tech Lead) — Iteration {iteration}")

        # Read current workspace files for context
        game_code = ""
        test_code = ""
        game_path = WORKSPACE / "tamagotchi.py"
        test_path = WORKSPACE / "test_tamagotchi.py"
        if game_path.exists():
            game_code = game_path.read_text()
        if test_path.exists():
            test_code = test_path.read_text()

        tl_input = (
            "You are a Tech Lead evaluating the team's work on a Tamagotchi game.\n\n"
            f"Review report:\n{review_report}\n\n"
            f"Current code ({len(game_code)} chars):\n"
            f"```python\n{game_code[:3000]}\n```\n\n"
            f"Current tests ({len(test_code)} chars):\n"
            f"```python\n{test_code[:2000]}\n```\n\n"
            'Respond with ONLY a JSON object:\n'
            '{"verdict": "APPROVED" or "NEEDS_WORK", '
            '"feedback": "specific feedback"}\n\n'
            "APPROVED if: code runs, tests pass, game loop works.\n"
            "NEEDS_WORK if: any crashes or missing features."
        )

        # Create a single-agent workflow for Tech Lead
        from miniautogen.cli.config import FlowConfig
        tl_flow = FlowConfig(
            mode="workflow",
            participants=["tech_lead"],
        )

        print("  Tech Lead evaluating...")
        tl_result = await runner.run_from_config(
            flow_config=tl_flow,
            agent_specs=agent_specs,
            workspace=WORKSPACE,
            config=config,
            input_text=tl_input,
        )

        # Parse verdict from Tech Lead output
        tl_output = str(tl_result.output) if tl_result.output else ""
        verdict = "NEEDS_WORK"
        feedback = ""
        try:
            raw = tl_output
            if "```" in raw:
                for part in raw.split("```"):
                    s = part.strip()
                    if s.startswith("json"):
                        s = s[4:].strip()
                    if s.startswith("{"):
                        raw = s
                        break
            parsed = json.loads(raw)
            verdict = parsed.get("verdict", "NEEDS_WORK")
            feedback = parsed.get("feedback", "")
        except (json.JSONDecodeError, AttributeError):
            feedback = f"Could not parse Tech Lead response: {tl_output[:200]}"

        icon = "APPROVED" if verdict == "APPROVED" else "NEEDS_WORK"
        print(f"\n  Verdict: {icon}")
        if feedback:
            print(f"  Feedback: {feedback[:150]}")

        if verdict == "APPROVED":
            break

    # ── Final summary ────────────────────────────────────────────
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    banner("DEVELOPMENT COMPLETE")
    print(f"  Iterations:   {iteration}/{MAX_ITERATIONS}")
    print(f"  Total events: {len(event_sink.events)}")
    print(f"  Total time:   {minutes}m {seconds}s")
    print(f"  Result:       {verdict}")

    # Event breakdown
    event_counts: dict[str, int] = {}
    for ev in event_sink.events:
        event_counts[ev.type] = event_counts.get(ev.type, 0) + 1

    print("\n  Event breakdown:")
    for etype, count in sorted(event_counts.items()):
        print(f"    {etype:40s} {count}")

    if verdict == "APPROVED" and game_path.exists():
        print(f"\n  Play your game:")
        print(f"    python {game_path}")
    else:
        print(f"\n  Check workspace/ for partial results.")


if __name__ == "__main__":
    asyncio.run(main())
