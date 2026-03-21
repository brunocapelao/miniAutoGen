"""Flow CRUD wizard — 3-step modal for creating or editing a flow.

Steps:
    1. Basics        — name and mode (workflow / deliberation)
    2. Participants   — select agents to include (min 2)
    3. Leader         — pick a leader (deliberation only; skipped for workflow)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    SelectionList,
    Static,
)


class FlowWizard(ModalScreen[dict | None]):
    """Three-step modal wizard to create or edit a flow (pipeline).

    Constructor
    -----------
    edit_name : str | None
        When *None*, the wizard creates a new flow.
        When set, the wizard pre-fills fields from
        ``provider.get_pipeline(edit_name)`` for editing.

    Result
    ------
    Dismisses with a dict
    ``{"name", "mode", "participants", "leader"}`` on successful
    submission, or ``None`` when cancelled.
    ``leader`` is ``None`` for workflow mode.
    """

    DEFAULT_CSS = """
    FlowWizard {
        align: center middle;
    }

    FlowWizard > Vertical {
        width: 70;
        height: auto;
        max-height: 35;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    FlowWizard .step-indicator {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    FlowWizard .step-title {
        text-align: center;
        margin-bottom: 1;
    }

    FlowWizard .step-container {
        height: auto;
        padding: 0 1;
    }

    FlowWizard .button-bar {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    FlowWizard .button-bar Button {
        margin-left: 1;
    }

    FlowWizard Input.invalid {
        border: tall $error;
    }

    FlowWizard SelectionList {
        height: 10;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    current_step: reactive[int] = reactive(1)

    def __init__(self, edit_name: str | None = None) -> None:
        super().__init__()
        self._edit_name = edit_name
        self._mode: str = "workflow"

    # ------------------------------------------------------------------
    # Provider helper
    # ------------------------------------------------------------------

    @property
    def provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    # ------------------------------------------------------------------
    # Dynamic step count
    # ------------------------------------------------------------------

    @property
    def _total_steps(self) -> int:
        """Return 3 for deliberation mode, 2 for workflow."""
        return 3 if self._mode == "deliberation" else 2

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the wizard layout with all three steps."""
        title = (
            f"Edit Flow: {self._edit_name}"
            if self._edit_name
            else "New Flow"
        )
        with Vertical():
            yield Static(f"[bold]{title}[/bold]", classes="step-title")
            yield Static("", id="step-indicator", classes="step-indicator")

            # --- Step 1: Basics ---
            with Vertical(id="step-1", classes="step-container"):
                yield Label("Name")
                yield Input(
                    placeholder="Flow name",
                    id="field-name",
                    disabled=self._edit_name is not None,
                )
                yield Label("Mode")
                with RadioSet(id="field-mode"):
                    yield RadioButton("workflow", value=True, id="mode-workflow")
                    yield RadioButton("deliberation", id="mode-deliberation")

            # --- Step 2: Participants ---
            with Vertical(id="step-2", classes="step-container"):
                yield Label("Select Participants (at least 2)")
                yield SelectionList[str](id="field-participants")

            # --- Step 3: Leader (deliberation only) ---
            with Vertical(id="step-3", classes="step-container"):
                yield Label("Select Leader")
                yield Select[str](
                    [], id="field-leader", prompt="Choose leader"
                )

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
        # Populate participants list
        if self.provider is not None:
            try:
                agents = self.provider.get_agents()
                sel_list = self.query_one("#field-participants", SelectionList)
                items: list[tuple[str, str]] = []
                for agent in agents:
                    name = agent.get("name", "?")
                    role = agent.get("role", "")
                    display = f"{name} — {role}" if role else name
                    items.append((display, name))
                sel_list.add_options(items)
            except Exception:
                pass

        # Pre-fill for edit mode
        if self._edit_name and self.provider:
            self._load_edit_data()

        self._sync_step_visibility()

    def _load_edit_data(self) -> None:
        """Pre-fill fields from an existing flow/pipeline."""
        if not self._edit_name or not self.provider:
            return
        try:
            data = self.provider.get_pipeline(self._edit_name)
        except (KeyError, Exception):
            self.notify(
                f"Could not load flow '{self._edit_name}'",
                severity="error",
            )
            return

        # Name
        try:
            self.query_one("#field-name", Input).value = data.get("name", "")
        except Exception:
            pass

        # Mode
        mode = data.get("mode", "workflow")
        self._mode = mode
        try:
            if mode == "deliberation":
                self.query_one("#mode-deliberation", RadioButton).value = True
            else:
                self.query_one("#mode-workflow", RadioButton).value = True
        except Exception:
            pass

        # Participants
        participants = data.get("participants", [])
        if participants:
            try:
                sel_list = self.query_one(
                    "#field-participants", SelectionList
                )
                for idx in range(sel_list.option_count):
                    option = sel_list.get_option_at_index(idx)
                    if option.value in participants:
                        sel_list.select(option.value)
            except Exception:
                pass

        # Leader
        leader = data.get("leader")
        if leader:
            try:
                self.query_one("#field-leader", Select).value = leader
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Mode tracking
    # ------------------------------------------------------------------

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Track the selected mode when the RadioSet changes."""
        if event.radio_set.id == "field-mode":
            pressed = event.pressed
            if pressed.id == "mode-deliberation":
                self._mode = "deliberation"
            else:
                self._mode = "workflow"
            # Re-sync visibility because total steps may have changed
            self._sync_step_visibility()

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def watch_current_step(self) -> None:
        """React to step changes by toggling visibility."""
        self._sync_step_visibility()

    def _sync_step_visibility(self) -> None:
        """Show only the current step and update buttons."""
        total = self._total_steps

        for i in range(1, 4):
            try:
                container = self.query_one(f"#step-{i}")
                container.display = i == self.current_step
            except Exception:
                pass

        # Update step indicator
        try:
            indicator = self.query_one("#step-indicator", Static)
            indicator.update(f"Step {self.current_step} of {total}")
        except Exception:
            pass

        # Button visibility
        try:
            self.query_one("#btn-back", Button).display = self.current_step > 1
            self.query_one("#btn-next", Button).display = (
                self.current_step < total
            )
            self.query_one("#btn-create", Button).display = (
                self.current_step == total
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_step(self, step: int) -> list[str]:
        """Return validation errors for a given step."""
        errors: list[str] = []

        if step == 1:
            name_input = self.query_one("#field-name", Input)
            if not name_input.value.strip():
                errors.append("'Name' is required")
                name_input.add_class("invalid")
            else:
                name_input.remove_class("invalid")

        elif step == 2:
            sel_list = self.query_one("#field-participants", SelectionList)
            selected = sel_list.selected
            if len(selected) < 2:
                errors.append("Select at least 2 participants")

        elif step == 3:
            # Leader is required only in deliberation mode
            if self._mode == "deliberation":
                leader_sel = self.query_one("#field-leader", Select)
                if leader_sel.value == Select.BLANK:
                    errors.append("A leader is required for deliberation mode")

        return errors

    # ------------------------------------------------------------------
    # Transition helpers
    # ------------------------------------------------------------------

    def _populate_leader_options(self) -> None:
        """Populate the leader select with currently selected participants."""
        try:
            sel_list = self.query_one("#field-participants", SelectionList)
            leader_sel = self.query_one("#field-leader", Select)
            selected = sel_list.selected
            options: list[tuple[str, str]] = [
                (str(val), str(val)) for val in selected
            ]
            leader_sel.set_options(options)
        except Exception:
            pass

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
            next_step = self.current_step + 1
            # If moving to leader step, populate leader options
            if next_step == 3 and self._mode == "deliberation":
                self._populate_leader_options()
            self.current_step = next_step

        elif btn_id == "btn-create":
            self._do_submit()

    def _do_submit(self) -> None:
        """Collect all values and dismiss with result dict."""
        # Re-validate all steps
        for step in range(1, self._total_steps + 1):
            errors = self._validate_step(step)
            if errors:
                self.current_step = step
                for msg in errors:
                    self.notify(msg, severity="warning")
                return

        name = self.query_one("#field-name", Input).value.strip()

        sel_list = self.query_one("#field-participants", SelectionList)
        participants: list[str] = [str(val) for val in sel_list.selected]

        leader: str | None = None
        if self._mode == "deliberation":
            leader_sel = self.query_one("#field-leader", Select)
            if leader_sel.value != Select.BLANK:
                leader = str(leader_sel.value)

        self.dismiss(
            {
                "name": name,
                "mode": self._mode,
                "participants": participants,
                "leader": leader,
            }
        )

    # ------------------------------------------------------------------
    # Escape
    # ------------------------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel the wizard and dismiss with None."""
        self.dismiss(None)
