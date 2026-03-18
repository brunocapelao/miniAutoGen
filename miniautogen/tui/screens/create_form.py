"""Generic multi-step form screen for creating/editing resources.

Supports engine, agent, and pipeline resource types with
type-specific field configurations.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static


# Field definitions per resource type
_ENGINE_FIELDS = [
    {"name": "name", "label": "Engine Name", "type": "input", "required": True},
    {"name": "kind", "label": "Kind", "type": "select", "options": ["api", "local"], "default": "api"},
    {"name": "provider", "label": "Provider", "type": "input", "required": True, "placeholder": "e.g. litellm, openai"},
    {"name": "model", "label": "Model", "type": "input", "required": True, "placeholder": "e.g. gpt-4o-mini"},
    {"name": "endpoint", "label": "Endpoint (optional)", "type": "input", "placeholder": "https://..."},
    {"name": "api_key_env", "label": "API Key Env Var", "type": "input", "placeholder": "e.g. OPENAI_API_KEY"},
]

_AGENT_FIELDS = [
    {"name": "name", "label": "Agent Name", "type": "input", "required": True},
    {"name": "role", "label": "Role", "type": "input", "required": True, "placeholder": "e.g. planner, researcher"},
    {"name": "goal", "label": "Goal", "type": "input", "required": True, "placeholder": "Describe what this agent does"},
    {"name": "engine_profile", "label": "Engine Profile", "type": "engine_select"},
]

_PIPELINE_FIELDS = [
    {"name": "name", "label": "Pipeline Name", "type": "input", "required": True},
    {"name": "mode", "label": "Mode", "type": "select", "options": ["workflow", "deliberation", "loop", "composite"], "default": "workflow"},
    {"name": "target", "label": "Target (optional)", "type": "input", "placeholder": "module.path:callable"},
]

_FIELD_MAP = {
    "engine": _ENGINE_FIELDS,
    "agent": _AGENT_FIELDS,
    "pipeline": _PIPELINE_FIELDS,
}


class CreateFormScreen(ModalScreen[bool]):
    """Multi-field form screen for creating or editing resources.

    Dismissed with True on successful create/edit, False on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self,
        resource_type: str,
        edit_name: str | None = None,
    ) -> None:
        super().__init__()
        self._resource_type = resource_type
        self._edit_name = edit_name
        self._fields = _FIELD_MAP.get(resource_type, [])

    @property
    def provider(self):
        """Access the DashDataProvider from the app."""
        return getattr(self.app, "_provider", None)

    def compose(self) -> ComposeResult:
        title = f"{'Edit' if self._edit_name else 'New'} {self._resource_type.title()}"
        yield Header()
        with Vertical(id="form-container"):
            yield Static(f"[bold]{title}[/bold]", id="form-title")

            for field in self._fields:
                yield Label(field["label"])
                ftype = field.get("type", "input")
                field_id = f"field-{field['name']}"

                if ftype == "select":
                    options = [(opt, opt) for opt in field.get("options", [])]
                    default = field.get("default", Select.BLANK)
                    yield Select(options, id=field_id, value=default)
                elif ftype == "engine_select":
                    # Dynamic: populated on mount
                    yield Select([], id=field_id)
                else:
                    placeholder = field.get("placeholder", "")
                    disabled = (self._edit_name is not None and field["name"] == "name")
                    yield Input(
                        placeholder=placeholder,
                        id=field_id,
                        disabled=disabled,
                    )

            yield Button("Save", id="btn-save", variant="primary")
            yield Button("Cancel", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        """Populate dynamic selects and load edit data."""
        # Populate engine_select fields
        if self.provider is not None:
            for field in self._fields:
                if field.get("type") == "engine_select":
                    field_id = f"field-{field['name']}"
                    try:
                        select = self.query_one(f"#{field_id}", Select)
                        engines = self.provider.get_engines()
                        options = [(e["name"], e["name"]) for e in engines]
                        select.set_options(options)
                    except Exception:
                        pass

        # Load existing data for edit mode
        if self._edit_name and self.provider:
            self._load_edit_data()

    def _load_edit_data(self) -> None:
        """Load existing resource data into form fields."""
        if not self._edit_name or not self.provider:
            return

        try:
            if self._resource_type == "engine":
                data = self.provider.get_engine(self._edit_name)
            elif self._resource_type == "agent":
                data = self.provider.get_agent(self._edit_name)
            elif self._resource_type == "pipeline":
                data = self.provider.get_pipeline(self._edit_name)
            else:
                return
        except (KeyError, Exception):
            self.notify(f"Could not load {self._resource_type}", severity="error")
            return

        for field in self._fields:
            field_id = f"field-{field['name']}"
            value = data.get(field["name"])
            if value is None:
                continue
            try:
                widget = self.query_one(f"#{field_id}")
                if isinstance(widget, Input):
                    widget.value = str(value)
                elif isinstance(widget, Select):
                    widget.value = str(value)
            except Exception:
                pass

    def _collect_values(self) -> dict:
        """Collect all field values from the form."""
        values = {}
        for field in self._fields:
            field_id = f"field-{field['name']}"
            try:
                widget = self.query_one(f"#{field_id}")
                if isinstance(widget, Input):
                    val = widget.value.strip()
                    if val:
                        values[field["name"]] = val
                elif isinstance(widget, Select):
                    if widget.value != Select.BLANK:
                        values[field["name"]] = widget.value
            except Exception:
                pass
        return values

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle save/cancel buttons."""
        if event.button.id == "btn-cancel":
            self.dismiss(False)
            return

        if event.button.id == "btn-save":
            self._do_save()

    def _do_save(self) -> None:
        """Validate and save the resource."""
        if self.provider is None:
            self.notify("No project found", severity="error")
            return

        values = self._collect_values()

        # Check required fields
        for field in self._fields:
            if field.get("required") and field["name"] not in values:
                self.notify(f"'{field['label']}' is required", severity="warning")
                return

        try:
            if self._edit_name:
                self._do_update(values)
            else:
                self._do_create(values)
            self.dismiss(True)
        except (ValueError, KeyError) as exc:
            self.notify(str(exc), severity="error")

    def _do_create(self, values: dict) -> None:
        """Create a new resource."""
        if self._resource_type == "engine":
            name = values.pop("name")
            self.provider.create_engine(name, **values)
            self.notify(f"Engine '{name}' created")
        elif self._resource_type == "agent":
            name = values.pop("name")
            self.provider.create_agent(name, **values)
            self.notify(f"Agent '{name}' created")
        elif self._resource_type == "pipeline":
            name = values.pop("name")
            self.provider.create_pipeline(name, **values)
            self.notify(f"Pipeline '{name}' created")

    def _do_update(self, values: dict) -> None:
        """Update an existing resource."""
        values.pop("name", None)  # Name is not updatable
        if self._resource_type == "engine":
            self.provider.update_engine(self._edit_name, **values)
            self.notify(f"Engine '{self._edit_name}' updated")
        elif self._resource_type == "agent":
            self.provider.update_agent(self._edit_name, **values)
            self.notify(f"Agent '{self._edit_name}' updated")
        elif self._resource_type == "pipeline":
            self.provider.update_pipeline(self._edit_name, **values)
            self.notify(f"Pipeline '{self._edit_name}' updated")

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(False)
