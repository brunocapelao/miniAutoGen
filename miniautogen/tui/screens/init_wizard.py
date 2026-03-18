"""Init wizard screen for bootstrapping a new project from TUI.

If no project config is found when the TUI launches, this wizard
guides the user through creating a new project.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class InitWizardScreen(ModalScreen[bool]):
    """Project initialization wizard.

    Collects project name, default model, and provider, then
    delegates to init_project.scaffold_project.

    Dismissed with True on success, False on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wizard-container"):
            yield Static(
                "[bold]Welcome to MiniAutoGen![/bold]\n\n"
                "No project found. Let's create one.",
                id="wizard-intro",
            )
            yield Label("Project Name")
            yield Input(placeholder="my-project", id="wizard-name")
            yield Label("Default Model")
            yield Input(placeholder="gpt-4o-mini", id="wizard-model", value="gpt-4o-mini")
            yield Label("Default Provider")
            yield Input(placeholder="litellm", id="wizard-provider", value="litellm")
            yield Button("Create Project", id="btn-create", variant="primary")
            yield Button("Cancel", id="btn-cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle create/cancel buttons."""
        if event.button.id == "btn-cancel":
            self.dismiss(False)
            return

        if event.button.id == "btn-create":
            self._do_create()

    def _do_create(self) -> None:
        """Scaffold the project."""
        name_input = self.query_one("#wizard-name", Input)
        model_input = self.query_one("#wizard-model", Input)
        provider_input = self.query_one("#wizard-provider", Input)

        name = name_input.value.strip()
        model = model_input.value.strip() or "gpt-4o-mini"
        provider = provider_input.value.strip() or "litellm"

        if not name:
            self.notify("Project name is required", severity="warning")
            return

        try:
            from miniautogen.cli.services.init_project import scaffold_project

            target_dir = Path.cwd()
            scaffold_project(
                name,
                target_dir,
                model=model,
                provider=provider,
                include_examples=True,
            )
            self.notify(f"Project '{name}' created at {target_dir / name}")
            self.dismiss(True)
        except (ValueError, FileExistsError) as exc:
            self.notify(str(exc), severity="error")

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(False)
