"""miniautogen completions command.

Generate shell completion scripts for bash, zsh, and fish.
"""

from __future__ import annotations

import click


_INSTRUCTIONS = {
    "bash": 'Add to ~/.bashrc:\n  eval "$(_MINIAUTOGEN_COMPLETE=bash_source miniautogen)"',
    "zsh": 'Add to ~/.zshrc:\n  eval "$(_MINIAUTOGEN_COMPLETE=zsh_source miniautogen)"',
    "fish": 'Save to ~/.config/fish/completions/miniautogen.fish:\n  _MINIAUTOGEN_COMPLETE=fish_source miniautogen | source',
}


@click.command("completions")
@click.argument(
    "shell",
    type=click.Choice(["bash", "zsh", "fish"]),
)
def completions_command(shell: str) -> None:
    """Generate shell completion script.

    Usage:
      miniautogen completions bash >> ~/.bashrc
      miniautogen completions zsh >> ~/.zshrc
      miniautogen completions fish > ~/.config/fish/completions/miniautogen.fish
    """
    import os
    import subprocess
    import sys

    env_var = f"_MINIAUTOGEN_COMPLETE={shell}_source"
    env = {**os.environ, env_var: "1"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "miniautogen.cli.main"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            click.echo(result.stdout)
        else:
            click.echo(f"# {_INSTRUCTIONS[shell]}")
    except Exception:
        click.echo(f"# {_INSTRUCTIONS[shell]}")
