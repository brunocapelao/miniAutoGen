"""Generate a smoke visual SVG of the Rich Live CLI UI.

Usage:
    uv run python scripts/rich_live_demo.py

Output: docs/assets/rich-live-demo.svg
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import deque

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def build_demo_panel() -> Panel:
    """Recreate the final state of a 3-agent deliberation panel."""
    elapsed_str = "03:47"

    header = (
        f"miniautogen run · deliberation-demo · run_id=abc12345 · elapsed={elapsed_str}"
    )

    body = Text()
    body.append("\n")
    body.append("▶ ", style="bold cyan")
    body.append("Advogado Sénior", style="bold")
    body.append("  · Review", style="dim")
    body.append("  · Round 4/5", style="dim")
    body.append("\n\n")

    thoughts = deque(
        [
            "O artigo 12 da LGPD impede o tratamento de dados sensíveis sem",
            "consentimento explícito. A redação atual do contrato viola",
            "este princípio ao usar 'consentimento implícito' no §3.",
        ],
        maxlen=3,
    )
    for line in thoughts:
        body.append("  └─ ", style="dim")
        body.append(f"{line}\n")

    footer = Text(
        "\nEvents: 142  ·  Press Ctrl+C to cancel & save",
        style="dim",
    )
    body.append(footer)
    return Panel(body, title=header, border_style="cyan", padding=(0, 1))


def main() -> None:
    output_path = Path(__file__).resolve().parent.parent / "docs" / "assets"
    output_path.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, force_terminal=True, width=88)
    panel = build_demo_panel()
    console.print(panel)

    svg = console.export_svg(title="miniautogen run — deliberation-demo")
    svg_path = output_path / "rich-live-demo.svg"
    svg_path.write_text(svg)
    print(f"SVG saved to {svg_path}")

    html = console.export_html()
    html_path = output_path / "rich-live-demo.html"
    html_path.write_text(html)
    print(f"HTML saved to {html_path}")


if __name__ == "__main__":
    main()
