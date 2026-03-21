"""Two-step modal wizard for configuring AI engines.

Step 1 (Discovery): Shows auto-discovered engines with status indicators.
Step 2 (Manual Creation): Form for creating a new engine profile.

Dismissed with a result dict on create/select, or None on cancel.
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

logger = logging.getLogger(__name__)

# Provider options for the creation form
_PROVIDER_OPTIONS: list[tuple[str, str]] = [
    ("openai", "openai"),
    ("anthropic", "anthropic"),
    ("gemini-cli", "gemini-cli"),
    ("ollama", "ollama"),
    ("litellm", "litellm"),
]


class EngineWizard(ModalScreen[dict[str, Any] | None]):
    """Two-step modal wizard for engine configuration.

    Step 1 displays auto-discovered engines and allows selecting one
    or navigating to Step 2 for manual creation.

    Step 2 provides a form to define a new engine profile.

    Args:
        edit_name: If provided, pre-fills the creation form with
            data from the named engine (edit mode).
    """

    DEFAULT_CSS = """
    EngineWizard {
        align: center middle;
    }

    EngineWizard > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    EngineWizard .wizard-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    EngineWizard .engine-item {
        height: 3;
        padding: 0 1;
        margin-bottom: 0;
    }

    EngineWizard .engine-item:hover {
        background: $primary 20%;
    }

    EngineWizard .engine-configured {
        color: $success;
    }

    EngineWizard .engine-discovered {
        color: $text-muted;
    }

    EngineWizard VerticalScroll {
        height: auto;
        max-height: 16;
        margin-bottom: 1;
    }

    EngineWizard .form-field {
        margin-bottom: 1;
    }

    EngineWizard Input.invalid {
        border: tall $error;
    }

    EngineWizard Select.invalid {
        border: tall $error;
    }

    EngineWizard Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    EngineWizard Button {
        margin-left: 1;
    }

    EngineWizard .step-hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, edit_name: str | None = None) -> None:
        """Initialize the engine wizard.

        Args:
            edit_name: Optional engine name to pre-fill for editing.
        """
        super().__init__()
        self._edit_name = edit_name
        self._engines: list[dict[str, Any]] = []
        self._configured_names: set[str] = set()

    @property
    def provider(self) -> Any | None:
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    def compose(self) -> ComposeResult:
        """Compose the wizard layout with both steps."""
        with Vertical():
            # Step 1: Discovery
            with Vertical(id="step-discovery"):
                yield Static("Configure Engine", classes="wizard-title")
                yield VerticalScroll(id="engine-list")
                with Horizontal():
                    yield Button("Add New Engine", id="btn-add-new", variant="primary")
                    yield Button("Cancel", id="btn-cancel-discovery")

            # Step 2: Manual Creation
            with Vertical(id="step-creation", classes="step-hidden"):
                yield Static("New Engine", classes="wizard-title")

                yield Label("Name *", classes="form-field")
                yield Input(
                    placeholder="e.g. my-engine",
                    id="field-name",
                )

                yield Label("Provider *", classes="form-field")
                yield Select(
                    _PROVIDER_OPTIONS,
                    id="field-provider",
                    prompt="Select provider",
                )

                yield Label("Model *", classes="form-field")
                yield Input(
                    placeholder="e.g. gpt-4o, claude-sonnet-4-20250514, gemini-2.5-pro",
                    id="field-model",
                )

                yield Label("API Key Env Var", classes="form-field")
                yield Input(
                    placeholder="e.g. OPENAI_API_KEY",
                    id="field-api-key-env",
                )

                yield Label("Endpoint URL", classes="form-field")
                yield Input(
                    placeholder="e.g. https://api.example.com/v1",
                    id="field-endpoint",
                )

                with Horizontal():
                    yield Button("Back", id="btn-back")
                    yield Button("Create", id="btn-create", variant="primary")

    def on_mount(self) -> None:
        """Load engines and populate the discovery list."""
        if self._edit_name:
            self._show_step("creation")
            self._prefill_edit_data()
        else:
            self._populate_engine_list()

    def _populate_engine_list(self) -> None:
        """Fetch engines from the provider and populate the discovery list."""
        engine_list = self.query_one("#engine-list", VerticalScroll)
        engine_list.remove_children()

        if self.provider is None:
            engine_list.mount(
                Static("[dim]No project loaded[/dim]", classes="engine-item")
            )
            return

        try:
            self._engines = self.provider.get_engines()
        except Exception:
            logger.exception("Failed to load engines")
            self._engines = []

        if not self._engines:
            engine_list.mount(
                Static(
                    "[dim]No engines discovered. Add one manually.[/dim]",
                    classes="engine-item",
                )
            )
            return

        # Determine which engines are configured (from YAML)
        self._configured_names = {
            eng.get("name", "")
            for eng in self._engines
            if eng.get("source") == "yaml"
        }

        for engine in self._engines:
            name = engine.get("name", "unknown")
            engine_provider = engine.get("provider", "?")
            model = engine.get("model", "?")
            source = engine.get("source", "?")
            is_configured = name in self._configured_names

            checkmark = "[green]\u2713[/green] " if is_configured else "  "
            source_tag = f"[dim]({source})[/dim]"
            css_class = "engine-configured" if is_configured else "engine-discovered"

            label = (
                f"{checkmark}[bold]{name}[/bold]  "
                f"{engine_provider} / {model}  {source_tag}"
            )
            item = Static(
                label,
                id=f"engine-{name}",
                classes=f"engine-item {css_class}",
            )
            engine_list.mount(item)

    def _prefill_edit_data(self) -> None:
        """Pre-fill the creation form with data from an existing engine."""
        if not self._edit_name or not self.provider:
            return

        try:
            data = self.provider.get_engine(self._edit_name)
        except (KeyError, Exception):
            logger.exception("Could not load engine '%s' for editing", self._edit_name)
            self.notify(f"Could not load engine '{self._edit_name}'", severity="error")
            return

        # Pre-fill fields
        name_input = self.query_one("#field-name", Input)
        name_input.value = data.get("name", "")
        name_input.disabled = True  # Cannot rename

        provider_select = self.query_one("#field-provider", Select)
        provider_val = data.get("provider", "")
        if provider_val:
            provider_select.value = provider_val

        model_input = self.query_one("#field-model", Input)
        model_input.value = data.get("model", "")

        api_key_input = self.query_one("#field-api-key-env", Input)
        api_key_input.value = data.get("api_key_env", "") or ""

        endpoint_input = self.query_one("#field-endpoint", Input)
        endpoint_input.value = data.get("endpoint", "") or ""

        # Update title for edit mode
        title = self.query_one("#step-creation .wizard-title", Static)
        title.update(f"Edit Engine: {self._edit_name}")

        # Change button text
        create_btn = self.query_one("#btn-create", Button)
        create_btn.label = "Save"

    def _show_step(self, step: str) -> None:
        """Toggle visibility between discovery and creation steps.

        Args:
            step: Either 'discovery' or 'creation'.
        """
        discovery = self.query_one("#step-discovery", Vertical)
        creation = self.query_one("#step-creation", Vertical)

        if step == "creation":
            discovery.add_class("step-hidden")
            creation.remove_class("step-hidden")
        else:
            creation.add_class("step-hidden")
            discovery.remove_class("step-hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button interactions across both steps."""
        button_id = event.button.id

        if button_id == "btn-cancel-discovery":
            self.dismiss(None)

        elif button_id == "btn-add-new":
            self._show_step("creation")

        elif button_id == "btn-back":
            self._clear_form()
            self._show_step("discovery")

        elif button_id == "btn-create":
            self._do_submit()

    def on_static_click(self, event: Static.Click) -> None:
        """Handle clicks on engine items in the discovery list."""
        widget = event.static
        widget_id = widget.id or ""

        if not widget_id.startswith("engine-"):
            return

        engine_name = widget_id[len("engine-"):]
        # Find the engine data
        for engine in self._engines:
            if engine.get("name") == engine_name:
                self.dismiss(
                    {
                        "name": engine.get("name", ""),
                        "provider": engine.get("provider", ""),
                        "model": engine.get("model", ""),
                        "api_key_env": engine.get("api_key_env"),
                        "endpoint": engine.get("endpoint"),
                    }
                )
                return

    def _validate(self) -> list[str]:
        """Validate required fields in the creation form.

        Returns:
            List of error messages. Empty if valid.
        """
        errors: list[str] = []

        name_input = self.query_one("#field-name", Input)
        if not name_input.value.strip():
            errors.append("'Name' is required")
            name_input.add_class("invalid")
        else:
            name_input.remove_class("invalid")

        provider_select = self.query_one("#field-provider", Select)
        if provider_select.value == Select.BLANK:
            errors.append("'Provider' is required")
            provider_select.add_class("invalid")
        else:
            provider_select.remove_class("invalid")

        model_input = self.query_one("#field-model", Input)
        if not model_input.value.strip():
            errors.append("'Model' is required")
            model_input.add_class("invalid")
        else:
            model_input.remove_class("invalid")

        return errors

    def _collect_values(self) -> dict[str, Any]:
        """Collect form field values into a result dict.

        Returns:
            Dictionary with engine configuration values.
        """
        name_input = self.query_one("#field-name", Input)
        provider_select = self.query_one("#field-provider", Select)
        model_input = self.query_one("#field-model", Input)
        api_key_input = self.query_one("#field-api-key-env", Input)
        endpoint_input = self.query_one("#field-endpoint", Input)

        api_key_val = api_key_input.value.strip() or None
        endpoint_val = endpoint_input.value.strip() or None

        return {
            "name": name_input.value.strip(),
            "provider": provider_select.value,
            "model": model_input.value.strip(),
            "api_key_env": api_key_val,
            "endpoint": endpoint_val,
        }

    def _do_submit(self) -> None:
        """Validate and dismiss with the collected engine data."""
        errors = self._validate()
        if errors:
            for msg in errors:
                self.notify(msg, severity="warning")
            return

        result = self._collect_values()
        self.dismiss(result)

    def _clear_form(self) -> None:
        """Reset all form fields to their default state."""
        try:
            self.query_one("#field-name", Input).value = ""
            self.query_one("#field-name", Input).disabled = False
            self.query_one("#field-provider", Select).value = Select.BLANK
            self.query_one("#field-model", Input).value = ""
            self.query_one("#field-api-key-env", Input).value = ""
            self.query_one("#field-endpoint", Input).value = ""

            # Remove any validation highlights
            for widget in self.query("Input.invalid, Select.invalid"):
                widget.remove_class("invalid")
        except Exception:
            pass

    def action_cancel(self) -> None:
        """Cancel and dismiss the wizard."""
        self.dismiss(None)
