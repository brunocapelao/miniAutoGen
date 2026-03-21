"""`:pipelines` view -- pipeline list with DataTable CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.worker import Worker
from textual.widgets import DataTable, Static

from miniautogen.tui.messages import RunCompleted
from miniautogen.tui.views.base import SecondaryView


class PipelinesView(SecondaryView):
    VIEW_TITLE = "Pipelines"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", show=True),
        Binding("n", "new_pipeline", "New", show=True),
        Binding("e", "edit_pipeline", "Edit", show=True),
        Binding("d", "delete_pipeline", "Delete", show=True),
        Binding("x", "run_pipeline", "Run", show=True),
        Binding("c", "cancel_run", "Cancel", show=False),
        Binding("r", "refresh_pipelines", "Refresh", show=True),
        Binding("f5", "refresh_pipelines", "Refresh", show=False),
    ]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._active_worker: Worker | None = None

    def compose_content(self) -> ComposeResult:
        yield Static(
            "[dim]Keys: [b]n[/b]ew  [b]e[/b]dit  [b]d[/b]elete  [b]x[/b] run  [b]r[/b]efresh[/dim]",
            id="pipelines-hint",
        )
        table = DataTable(id="pipelines-table")
        table.add_columns("Name", "Target", "Mode", "Agents", "Status")
        yield table
        yield Static(
            "Nenhum flow definido. Pressione [bold]n[/bold] para criar.",
            id="pipelines-empty",
            classes="empty-state",
        )

    def on_mount(self) -> None:
        """Populate table with pipeline data on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload pipeline data into the table."""
        table = self.query_one("#pipelines-table", DataTable)
        table.clear()
        if self.provider is None:
            self._set_empty_visible(True)
            return
        for pipeline in self.provider.get_pipelines():
            participants = pipeline.get("participants", [])
            agents_str = ", ".join(participants) if participants else "(none)"
            table.add_row(
                pipeline.get("name", "?"),
                pipeline.get("target", "?"),
                pipeline.get("mode", "?"),
                agents_str,
                "ready",
            )
        self._set_empty_visible(table.row_count == 0)

    def _set_empty_visible(self, visible: bool) -> None:
        """Show or hide the empty-state message."""
        try:
            empty = self.query_one("#pipelines-empty", Static)
            empty.display = visible
        except Exception:
            pass

    def _get_selected_name(self) -> str | None:
        """Get the name from the currently selected row."""
        table = self.query_one("#pipelines-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            return str(row[0]) if row else None
        return None

    def action_new_pipeline(self) -> None:
        """Open pipeline creation form."""
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline"),
            callback=self._on_form_result,
        )

    def action_edit_pipeline(self) -> None:
        """Open pipeline edit form."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        from miniautogen.tui.screens.create_form import CreateFormScreen

        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_pipeline(self) -> None:
        """Delete selected pipeline with confirmation."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog

        self.app.push_screen(
            ConfirmDialog(f"Excluir flow '{name}'? Esta ação não pode ser desfeita."),
            callback=lambda confirmed: self._do_delete_pipeline(name) if confirmed else None,
        )

    def _do_delete_pipeline(self, name: str) -> None:
        """Perform the actual pipeline deletion after confirmation."""
        if self.provider is None:
            return
        try:
            self.provider.delete_pipeline(name)
            self.notify(f"Pipeline '{name}' deleted")
            self._refresh_table()
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def action_run_pipeline(self) -> None:
        """Prompt for optional input text, then run the selected pipeline."""
        name = self._get_selected_name()
        if not name:
            self.notify("No pipeline selected", severity="warning")
            return
        if self.provider is None:
            self.notify("No project loaded", severity="error")
            return

        from miniautogen.tui.screens.input_dialog import InputDialog

        self.app.push_screen(
            InputDialog(
                title=f"Run pipeline: {name}",
                placeholder="Input text (optional)",
            ),
            callback=lambda text: self._start_pipeline_run(name, text),
        )

    def _start_pipeline_run(self, name: str, pipeline_input: str | None) -> None:
        """Start the pipeline worker after the input dialog is dismissed."""
        self.notify(f"Starting pipeline '{name}'...")

        async def _run() -> None:
            """Background worker coroutine for pipeline execution."""
            try:
                event_sink = getattr(self.app, "_event_sink", None)
                result = await self.provider.run_pipeline(
                    name,
                    event_sink=event_sink,
                    pipeline_input=pipeline_input,
                )
                status = result.get("status", "unknown")
                if status == "completed":
                    self.app.notify(f"Pipeline '{name}' completed")
                else:
                    error = result.get("error", "unknown error")
                    self.app.notify(
                        f"Pipeline '{name}' failed: {error}",
                        severity="error",
                    )
                self.app.post_message(RunCompleted(pipeline_name=name, status=status))
            finally:
                self._active_worker = None
                self.app.refresh_bindings()

        worker = self.app.run_worker(_run(), exclusive=False)
        self._active_worker = worker
        self.app.refresh_bindings()

    def action_cancel_run(self) -> None:
        """Cancel the currently running pipeline worker."""
        if self._active_worker is None:
            self.notify("No pipeline is running", severity="warning")
            return
        self._active_worker.cancel()
        self._active_worker = None
        self.app.refresh_bindings()
        self.notify("Run cancelled", severity="warning")

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Control which bindings are shown/enabled based on runtime state.

        The 'cancel_run' binding is only shown while a worker is active.
        The 'run_pipeline' binding is disabled while a worker is active
        to prevent concurrent runs.
        """
        if action == "cancel_run":
            return self._active_worker is not None
        if action == "run_pipeline":
            return self._active_worker is None
        return True

    def action_refresh_pipelines(self) -> None:
        """Refresh the pipelines table."""
        self._refresh_table()
        self.notify("Refreshed")

    def _on_form_result(self, result: object) -> None:
        """Callback from form screen."""
        if result:
            self._refresh_table()
