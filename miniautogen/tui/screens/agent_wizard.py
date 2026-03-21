"""Agent CRUD wizard — 3-step modal for creating or editing an agent.

Steps:
    1. Identity  — name and role
    2. Goal      — free-text goal description
    3. Engine    — choose an engine profile
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea


_TOTAL_STEPS = 3


class AgentWizard(ModalScreen[dict | None]):
    """Three-step modal wizard to create or edit an agent.

    Constructor
    -----------
    edit_name : str | None
        When *None*, the wizard creates a new agent.
        When set, the wizard pre-fills fields from
        ``provider.get_agent(edit_name)`` for editing.

    Result
    ------
    Dismisses with a dict ``{"name", "role", "goal", "engine_profile"}``
    on successful submission, or ``None`` when cancelled.
    """

    DEFAULT_CSS = """
    AgentWizard {
        align: center middle;
    }

    AgentWizard > Vertical {
        width: 70;
        height: auto;
        max-height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    AgentWizard .step-indicator {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    AgentWizard .step-title {
        text-align: center;
        margin-bottom: 1;
    }

    AgentWizard .step-container {
        height: auto;
        max-height: 18;
        padding: 0 1;
    }

    AgentWizard TextArea {
        height: 8;
        max-height: 8;
    }

    AgentWizard .button-bar {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    AgentWizard .button-bar Button {
        margin-left: 1;
    }

    AgentWizard Input.invalid {
        border: tall $error;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    current_step: reactive[int] = reactive(1)

    def __init__(self, edit_name: str | None = None) -> None:
        super().__init__()
        self._edit_name = edit_name
        self._collected: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Provider helper
    # ------------------------------------------------------------------

    @property
    def provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the wizard layout with all three steps (visibility toggled)."""
        title = (
            f"Edit Agent: {self._edit_name}"
            if self._edit_name
            else "New Agent"
        )
        with Vertical():
            yield Static(f"[bold]{title}[/bold]", classes="step-title")
            yield Static("", id="step-indicator", classes="step-indicator")

            # --- Step 1: Identity ---
            with Vertical(id="step-1", classes="step-container"):
                yield Label("Name")
                yield Input(
                    placeholder="Agent name",
                    id="field-name",
                    disabled=self._edit_name is not None,
                )
                yield Label("Role")
                yield Input(
                    placeholder="e.g. planner, researcher, coder",
                    id="field-role",
                )

            # --- Step 2: Goal ---
            with Vertical(id="step-2", classes="step-container"):
                yield Label("Goal")
                yield TextArea(
                    id="field-goal",
                )

            # --- Step 3: Engine ---
            with Vertical(id="step-3", classes="step-container"):
                yield Label("Engine Profile")
                yield Select[str]([], id="field-engine", prompt="Choose engine")

            # --- Buttons ---
            with Horizontal(classes="button-bar"):
                yield Button("Back", id="btn-back", variant="default")
                yield Button("Next", id="btn-next", variant="primary")
                yield Button("Create", id="btn-create", variant="success")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate dynamic widgets and load edit data."""
        # Set placeholder on TextArea (post-mount because TextArea needs it)
        try:
            goal_ta = self.query_one("#field-goal", TextArea)
            goal_ta.text = ""
        except Exception:
            pass

        # Populate engine select
        if self.provider is not None:
            try:
                engines = self.provider.get_engines()
                options: list[tuple[str, str]] = []
                for eng in engines:
                    label_parts = [eng.get("name", "?")]
                    if eng.get("provider"):
                        label_parts.append(eng["provider"])
                    if eng.get("model"):
                        label_parts.append(eng["model"])
                    display = " | ".join(label_parts)
                    options.append((display, eng["name"]))
                sel = self.query_one("#field-engine", Select)
                sel.set_options(options)
            except Exception:
                pass

        # Pre-fill for edit mode
        if self._edit_name and self.provider:
            self._load_edit_data()

        self._sync_step_visibility()

    def _load_edit_data(self) -> None:
        """Pre-fill fields from an existing agent definition."""
        if not self._edit_name or not self.provider:
            return
        try:
            data = self.provider.get_agent(self._edit_name)
        except (KeyError, Exception):
            self.notify(
                f"Could not load agent '{self._edit_name}'",
                severity="error",
            )
            return

        try:
            self.query_one("#field-name", Input).value = data.get("name", "")
        except Exception:
            pass
        try:
            self.query_one("#field-role", Input).value = data.get("role", "")
        except Exception:
            pass
        try:
            goal_ta = self.query_one("#field-goal", TextArea)
            goal_ta.text = data.get("goal", "")
        except Exception:
            pass
        try:
            engine = data.get("engine_profile")
            if engine:
                self.query_one("#field-engine", Select).value = engine
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def watch_current_step(self) -> None:
        """React to step changes by toggling visibility."""
        self._sync_step_visibility()

    def _sync_step_visibility(self) -> None:
        """Show only the current step container and update buttons."""
        for i in range(1, _TOTAL_STEPS + 1):
            try:
                container = self.query_one(f"#step-{i}")
                container.display = i == self.current_step
            except Exception:
                pass

        # Update step indicator
        try:
            indicator = self.query_one("#step-indicator", Static)
            indicator.update(
                f"Step {self.current_step} of {_TOTAL_STEPS}"
            )
        except Exception:
            pass

        # Button visibility
        try:
            self.query_one("#btn-back", Button).display = self.current_step > 1
            self.query_one("#btn-next", Button).display = (
                self.current_step < _TOTAL_STEPS
            )
            self.query_one("#btn-create", Button).display = (
                self.current_step == _TOTAL_STEPS
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_step(self, step: int) -> list[str]:
        """Return a list of validation error strings for *step*."""
        errors: list[str] = []
        if step == 1:
            name_input = self.query_one("#field-name", Input)
            name_val = name_input.value.strip()
            if not name_val:
                errors.append("'Name' is required")
                name_input.add_class("invalid")
            else:
                name_input.remove_class("invalid")
                # Uniqueness check for new agents
                if self._edit_name is None and self.provider is not None:
                    try:
                        existing = self.provider.get_agents()
                        names = {a.get("name") for a in existing}
                        if name_val in names:
                            errors.append(
                                f"Agent '{name_val}' already exists"
                            )
                            name_input.add_class("invalid")
                    except Exception:
                        pass

            role_input = self.query_one("#field-role", Input)
            if not role_input.value.strip():
                errors.append("'Role' is required")
                role_input.add_class("invalid")
            else:
                role_input.remove_class("invalid")

        elif step == 2:
            # Goal is optional but recommended — no hard validation
            pass

        elif step == 3:
            # Engine selection is optional — no hard validation
            pass

        return errors

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to navigation or submission."""
        btn_id = event.button.id
        if btn_id == "btn-back":
            if self.current_step > 1:
                self.current_step -= 1
        elif btn_id == "btn-next":
            errors = self._validate_step(self.current_step)
            if errors:
                for msg in errors:
                    self.notify(msg, severity="warning")
                return
            if self.current_step < _TOTAL_STEPS:
                self.current_step += 1
        elif btn_id == "btn-create":
            self._do_submit()

    def _do_submit(self) -> None:
        """Collect all values and dismiss with result dict."""
        # Validate step 1 fields even if we're on step 3
        errors = self._validate_step(1)
        if errors:
            self.current_step = 1
            for msg in errors:
                self.notify(msg, severity="warning")
            return

        name = self.query_one("#field-name", Input).value.strip()
        role = self.query_one("#field-role", Input).value.strip()

        goal_ta = self.query_one("#field-goal", TextArea)
        goal = goal_ta.text.strip()

        engine_sel = self.query_one("#field-engine", Select)
        engine_profile: str | None = (
            engine_sel.value
            if engine_sel.value != Select.BLANK
            else None
        )

        self.dismiss(
            {
                "name": name,
                "role": role,
                "goal": goal,
                "engine_profile": engine_profile,
            }
        )

    # ------------------------------------------------------------------
    # Escape
    # ------------------------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel the wizard and dismiss with None."""
        self.dismiss(None)
