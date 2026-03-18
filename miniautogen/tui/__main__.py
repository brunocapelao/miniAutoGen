"""Standalone entry point: python -m miniautogen.tui"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from miniautogen.tui.app import MiniAutoGenDash
    except ImportError:
        print(
            "MiniAutoGen TUI requires the 'tui' extra.\n"
            "Install with: pip install miniautogen[tui]",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = MiniAutoGenDash()
    app.run()


if __name__ == "__main__":
    main()
