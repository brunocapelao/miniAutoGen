"""Visual usability tests — captures SVG screenshots of all TUI states."""

import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from miniautogen.tui.app import MiniAutoGenDash

OUTPUT_DIR = Path("/Users/brunocapelao/Projects/miniAutoGen/.superpowers/brainstorm/48862-1774089727")


def create_test_project() -> Path:
    """Create a temporary project directory with config, agents, engines, flows."""
    tmp = Path(tempfile.mkdtemp(prefix="miniautogen_visual_"))

    # miniautogen.yaml (must match WorkspaceConfig schema)
    (tmp / "miniautogen.yaml").write_text("""
project:
  name: demo-project
  version: "0.1.0"
defaults:
  engine: gpt4o
engines:
  gpt4o:
    kind: api
    provider: litellm
    model: gpt-4o
  claude:
    kind: api
    provider: litellm
    model: claude-3-sonnet
  local_llm:
    kind: local
    provider: ollama
    model: llama3
flows:
  research-flow:
    mode: workflow
    participants:
      - planner
      - researcher
      - reviewer
  code-review:
    mode: deliberation
    participants:
      - reviewer
      - coder
""")

    # Agents directory
    agents_dir = tmp / "agents"
    agents_dir.mkdir()

    for name, role, engine in [
        ("planner", "Creative direction and planning", "gpt4o"),
        ("researcher", "Find sources and validate facts", "gpt4o"),
        ("reviewer", "Review PRs and find bugs", "claude"),
        ("coder", "Write implementation code", "gpt4o"),
    ]:
        (agents_dir / f"{name}.yaml").write_text(f"""
id: {name}
role: {role}
engine_profile: {engine}
goal: "{role}"
""")

    # Flows directory
    flows_dir = tmp / "flows"
    flows_dir.mkdir()

    (flows_dir / "research-flow.yaml").write_text("""
name: research-flow
mode: workflow
participants:
  - planner
  - researcher
  - reviewer
""")

    (flows_dir / "code-review.yaml").write_text("""
name: code-review
mode: deliberation
participants:
  - reviewer
  - coder
""")

    return tmp


async def capture_screenshot(project_root: Path, name: str, setup_fn=None, size=(160, 45)):
    """Capture a single screenshot."""
    app = MiniAutoGenDash(project_root=str(project_root))
    async with app.run_test(size=size) as pilot:
        await asyncio.sleep(0.5)  # Let mount complete
        if setup_fn:
            await setup_fn(pilot, app)
            await asyncio.sleep(0.3)
        svg = app.export_screenshot()
        (OUTPUT_DIR / f"{name}.svg").write_text(svg)
        print(f"  ✓ {name}.svg")


async def main():
    print("Creating test project...")
    project_root = create_test_project()
    print(f"  Project at: {project_root}\n")

    print("Capturing TUI screenshots...\n")

    tests = [
        ("01-workspace", "Workspace Tab (default)", None, (160, 45)),
        ("02-flows", "Flows Tab", lambda p, a: p.press("2"), (160, 45)),
        ("03-agents", "Agents Tab", lambda p, a: p.press("3"), (160, 45)),
        ("04-config", "Config Tab", lambda p, a: p.press("4"), (160, 45)),
        ("05-sidebar-hidden", "Sidebar Hidden", lambda p, a: p.press("t"), (160, 45)),
        ("06-narrow", "Narrow Terminal (80x30)", None, (80, 30)),
    ]

    results = []
    for filename, label, setup_fn, size in tests:
        try:
            print(f"  [{label}]")
            await capture_screenshot(project_root, filename, setup_fn, size)
            results.append((label, "PASS"))
        except Exception as e:
            print(f"  ✕ {label}: {e}")
            results.append((label, f"FAIL: {e}"))

    # Cleanup
    shutil.rmtree(project_root, ignore_errors=True)

    print(f"\n{'='*50}")
    passed = sum(1 for _, s in results if s == "PASS")
    print(f"Visual Tests: {passed}/{len(results)} passed")
    for label, status in results:
        symbol = "✓" if status == "PASS" else "✕"
        print(f"  {symbol} {label}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
