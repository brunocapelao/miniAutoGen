"""3-step modal wizard for running a pipeline/flow.

Step 1: Select a flow from available pipelines.
Step 2: Enter the input prompt / task description.
Step 3: Review and confirm before execution.

Dismisses with a dict ``{"flow": name, "input": prompt_text}`` on run,
or ``None`` on cancel / escape.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option


class RunFlowWizard(ModalScreen[dict | None]):
    """Multi-step wizard to select a flow, provide input, and launch a run.

    Returns a dict with ``flow`` (pipeline name) and ``input`` (prompt text)
    on successful submission, or ``None`` when cancelled.
    """

    DEFAULT_CSS = """
    RunFlowWizard {
        align: center middle;
    }

    RunFlowWizard > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    RunFlowWizard .step-indicator {
        color: $text-muted;
        margin-bottom: 1;
    }

    RunFlowWizard .wizard-title {
        text-style: bold;
        margin-bottom: 1;
    }

    RunFlowWizard .step-container {
        height: auto;
        max-height: 60%;
    }

    RunFlowWizard OptionList {
        height: auto;
        max-height: 16;
        margin-bottom: 1;
    }

    RunFlowWizard TextArea {
        height: 8;
        margin-bottom: 1;
    }

    RunFlowWizard .summary-text {
        margin-bottom: 1;
    }

    RunFlowWizard .button-bar {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    RunFlowWizard .button-bar Button {
        margin-left: 1;
    }

    RunFlowWizard .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    current_step: reactive[int] = reactive(1)
    """Which wizard step is currently displayed (1, 2, or 3)."""

    def __init__(self) -> None:
        super().__init__()
        self._pipelines: list[dict] = []
        self._selected_flow: dict | None = None

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
        with Vertical():
            yield Static("", id="step-indicator", classes="step-indicator")
            yield Static("", id="wizard-title", classes="wizard-title")

            # Step 1 -- Select Flow
            with Vertical(id="step-1", classes="step-container"):
                yield OptionList(id="flow-list")

            # Step 2 -- Input Prompt
            with Vertical(id="step-2", classes="step-container hidden"):
                yield TextArea(
                    id="prompt-input",
                )

            # Step 3 -- Confirm
            with Vertical(id="step-3", classes="step-container hidden"):
                yield Static("", id="summary-text", classes="summary-text")

            # Button bar (always visible)
            with Horizontal(classes="button-bar"):
                yield Button("Back", id="btn-back", classes="hidden")
                yield Button("Next", id="btn-next", variant="primary", disabled=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the flow list from the provider on mount."""
        self._load_pipelines()
        self._sync_step()

        # Set TextArea placeholder via its attribute
        try:
            text_area = self.query_one("#prompt-input", TextArea)
            text_area.load_text("")
        except Exception:
            pass

    def _load_pipelines(self) -> None:
        """Load available pipelines into the OptionList."""
        if self.provider is not None:
            self._pipelines = self.provider.get_pipelines()
        else:
            self._pipelines = []

        option_list = self.query_one("#flow-list", OptionList)
        option_list.clear_options()

        if not self._pipelines:
            option_list.add_option(
                Option("(no flows available)", id="__none__", disabled=True)
            )
            return

        for pipeline in self._pipelines:
            name = pipeline.get("name", "unnamed")
            mode = pipeline.get("mode", "?")
            participants = pipeline.get("participants", [])
            count = len(participants) if isinstance(participants, list) else 0
            label = f"{name}  [{mode}]  {count} participant(s)"
            option_list.add_option(Option(label, id=name))

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def watch_current_step(self, step: int) -> None:
        """React to step changes by updating visible containers."""
        self._sync_step()

    def _sync_step(self) -> None:
        """Show/hide containers and update indicator based on current_step."""
        step = self.current_step

        # Step indicator
        try:
            indicator = self.query_one("#step-indicator", Static)
            indicator.update(f"Step {step} of 3")
        except Exception:
            pass

        # Title per step
        titles = {
            1: "Run Flow",
            2: "What should the team work on?",
            3: "Ready to Run",
        }
        try:
            title_widget = self.query_one("#wizard-title", Static)
            title_widget.update(f"[bold]{titles.get(step, '')}[/bold]")
        except Exception:
            pass

        # Toggle step containers
        for i in range(1, 4):
            try:
                container = self.query_one(f"#step-{i}")
                if i == step:
                    container.remove_class("hidden")
                else:
                    container.add_class("hidden")
            except Exception:
                pass

        # Back button visibility
        try:
            back_btn = self.query_one("#btn-back", Button)
            if step > 1:
                back_btn.remove_class("hidden")
            else:
                back_btn.add_class("hidden")
        except Exception:
            pass

        # Next/Run button
        try:
            next_btn = self.query_one("#btn-next", Button)
            if step == 3:
                next_btn.label = "Run"
                next_btn.variant = "success"
                next_btn.disabled = False
            else:
                next_btn.label = "Next"
                next_btn.variant = "primary"
                # Disable Next on step 1 until a flow is selected
                if step == 1:
                    next_btn.disabled = self._selected_flow is None
                else:
                    next_btn.disabled = False
        except Exception:
            pass

        # Populate summary when entering step 3
        if step == 3:
            self._update_summary()

    def _update_summary(self) -> None:
        """Build and display the confirmation summary."""
        if self._selected_flow is None:
            return

        name = self._selected_flow.get("name", "?")
        mode = self._selected_flow.get("mode", "?")
        participants = self._selected_flow.get("participants", [])
        if isinstance(participants, list):
            participants_str = ", ".join(str(p) for p in participants)
        else:
            participants_str = str(participants)

        try:
            prompt_text = self.query_one("#prompt-input", TextArea).text.strip()
        except Exception:
            prompt_text = ""

        preview = prompt_text[:100]
        if len(prompt_text) > 100:
            preview += "..."

        summary_lines = [
            f"[bold]Flow:[/bold]         {name}",
            f"[bold]Mode:[/bold]         {mode}",
            f"[bold]Participants:[/bold] {participants_str or '(none)'}",
            f"[bold]Input:[/bold]        {preview or '(empty)'}",
        ]

        try:
            summary_widget = self.query_one("#summary-text", Static)
            summary_widget.update("\n".join(summary_lines))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Track which flow the user has highlighted/selected."""
        if event.option.id == "__none__":
            self._selected_flow = None
        else:
            for pipeline in self._pipelines:
                if pipeline.get("name") == event.option.id:
                    self._selected_flow = pipeline
                    break

        # Enable/disable Next based on selection
        if self.current_step == 1:
            try:
                next_btn = self.query_one("#btn-next", Button)
                next_btn.disabled = self._selected_flow is None
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Back / Next / Run button presses."""
        button_id = event.button.id

        if button_id == "btn-back":
            if self.current_step > 1:
                self.current_step -= 1
            return

        if button_id == "btn-next":
            if self.current_step == 1:
                if self._selected_flow is None:
                    self.notify("Please select a flow first.", severity="warning")
                    return
                self.current_step = 2

            elif self.current_step == 2:
                self.current_step = 3

            elif self.current_step == 3:
                self._do_run()
            return

    def _do_run(self) -> None:
        """Dismiss the wizard with the selected flow and input text."""
        if self._selected_flow is None:
            self.notify("No flow selected.", severity="error")
            return

        try:
            prompt_text = self.query_one("#prompt-input", TextArea).text.strip()
        except Exception:
            prompt_text = ""

        self.dismiss({
            "flow": self._selected_flow.get("name", ""),
            "input": prompt_text,
        })

    def action_cancel(self) -> None:
        """Cancel and dismiss with None."""
        self.dismiss(None)
