"""ConverterPanel widget — format selector + dynamic config form."""

from __future__ import annotations

import enum
import typing
from typing import Optional, Union

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Click, Key
from textual.message import Message
from textual.widgets import Button, Input, Label, Select, Static

from flync_converter.base import ConverterConfig
from flync_converter.registry import registry

from ..utils import cast_value, get_config_model
from .path_picker import PathPicker, PickMode


def _resolve_field_type(annotation):
    """Unwrap Optional/Union and return the inner type."""
    origin = getattr(annotation, "__origin__", None)
    if origin is Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return args[0] if args else annotation
    return annotation


#: Config fields managed by the stored configuration file or destination side,
#: never edited in the panel (mirrors the GUI panel).
_NON_EDITABLE_FIELDS = frozenset({"version", "report_enabled", "report_min_log_level", "report_dir", "persist_config"})


class _TitleAction(Static):
    """Compact keyboard-accessible action on the title row of a panel."""

    can_focus = True

    def on_click(self, _event: Click) -> None:
        self.activate()

    def on_key(self, event: Key) -> None:
        if event.key in {"enter", "space"}:
            event.stop()
            self.activate()

    def activate(self) -> None:
        """Run the action."""
        raise NotImplementedError


class CollapseToggle(_TitleAction):
    """Arrow that collapses its panel to the title row and expands it again."""

    def activate(self) -> None:
        panel = self.query_ancestor(ConverterPanel)
        panel.set_collapsed(not panel.is_collapsed)


class RemoveAction(_TitleAction):
    """Compact keyboard-accessible endpoint removal action."""

    class Pressed(Message):
        """Posted when the removal action is activated."""

        def __init__(self, action: RemoveAction) -> None:
            super().__init__()
            self.action = action

    def activate(self) -> None:
        self.post_message(self.Pressed(self))


class ConverterPanel(Vertical):
    """One half of the split-panel: format selector + dynamic config form."""

    DEFAULT_CSS = """
    ConverterPanel {
        width: 100%;
        height: auto;
        border: solid $accent;
        padding: 0;
        overflow-x: hidden;
    }

    ConverterPanel .title-row {
        width: 100%;
        height: 2;
        padding: 0 1;
        align: left middle;
    }

    ConverterPanel .collapse-toggle {
        width: 2;
        height: 1;
        color: $accent;
    }

    ConverterPanel .collapse-toggle:hover,
    ConverterPanel .collapse-toggle:focus {
        text-style: bold reverse;
    }

    ConverterPanel .panel-title {
        width: auto;
        height: 1;
        padding: 0;
        color: $accent;
        text-style: bold;
    }

    ConverterPanel .panel-summary {
        width: 1fr;
        height: 1;
        padding: 0 0 0 2;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }

    ConverterPanel .panel-body {
        width: 100%;
        height: auto;
    }

    ConverterPanel .remove-endpoint {
        width: 9;
        height: 1;
        margin: 0;
        padding: 0;
        content-align: right middle;
        color: $text-muted;
        text-style: none;
    }

    ConverterPanel .remove-endpoint:hover,
    ConverterPanel .remove-endpoint:focus {
        color: $error-lighten-2;
        text-style: bold;
    }


    ConverterPanel Select,
    ConverterPanel Input {
        width: 100%;
        height: 3;
        margin: 0;
    }

    ConverterPanel .path-row {
        width: 100%;
        height: auto;
    }

    ConverterPanel .path-row Input {
        width: 1fr;
    }

    ConverterPanel .browse-path {
        width: 10;
        min-width: 10;
        height: 3;
        margin: 0 0 0 1;
    }

    ConverterPanel #fields {
        width: 100%;
        height: auto;
    }

    ConverterPanel .field-label {
        width: 100%;
        height: 2;
        padding: 1 0 0 0;
        color: $text-muted;
    }

    ConverterPanel .error-msg {
        width: 100%;
        padding: 0;
        color: $error;
        height: auto;
    }
    """

    _ERROR_WIDGET_ID = "#error"

    class Changed(Message):
        """Posted when the selected converter type changes."""

        def __init__(self, panel: ConverterPanel, converter_type: Optional[str]) -> None:
            super().__init__()
            self.panel = panel
            self.converter_type = converter_type

        @property
        def control(self) -> ConverterPanel:
            """Return the ConverterPanel that posted this message."""
            return self.panel

    def __init__(self, title: str, default: Optional[str] = None, removable: bool = False, **kwargs) -> None:
        """Initialize the TUI converter panel.

        Args:
            title: Title label for the panel (e.g., "Source" or "Destination").
            default: Optional default converter to select.
            **kwargs: Additional widget arguments.
        """
        super().__init__(**kwargs)
        self._title = title
        self._default = default
        self._removable = removable
        self._collapsed = False
        self._converter_type: Optional[str] = None

    def set_title(self, title: str) -> None:
        """Update the visible endpoint title."""
        self._title = title
        if self.is_mounted:
            self.query_one(".panel-title", Label).update(title)

    def set_remove_enabled(self, enabled: bool) -> None:
        """Enable removal only while another endpoint of the role remains."""
        self._removable = enabled
        if self.is_mounted:
            self.query_one("#remove", RemoveAction).display = enabled

    def on_mount(self) -> None:
        """Apply the initial Remove visibility without reserving hidden space."""
        self.query_one("#remove", RemoveAction).display = self._removable
        self.set_collapsed(self._collapsed)

    @property
    def is_collapsed(self) -> bool:
        """Return whether the format selector and config fields are hidden."""
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Show or hide the format selector and config fields.

        A collapsed panel keeps its title row, with a summary of its format and
        path, and its error message. The field values are kept.
        """
        self._collapsed = collapsed
        if not self.is_mounted:
            return
        toggle = self.query_one("#collapse", CollapseToggle)
        toggle.update("▶" if collapsed else "▼")
        toggle.tooltip = "Expand" if collapsed else "Collapse"
        self.query_one(".panel-summary", Label).update(self.summary() if collapsed else "")
        self.query_one("#body", Vertical).display = not collapsed

    def summary(self) -> str:
        """Return the format and path of the endpoint, as shown when it is collapsed."""
        if self._converter_type is None:
            return "no format selected"
        path = next((widget.value.strip() for widget in self.query(f"#field-{self.id}-config_path").results(Input)), "")
        return f"{self._converter_type} · {path or 'no path'}"

    @property
    def converter_type(self) -> Optional[str]:
        """Return the currently selected converter type name, or None if none is selected."""
        return self._converter_type

    def compose(self) -> ComposeResult:  # NOSONAR
        """Build the panel: a title label, converter selector, dynamic config fields, and error display."""
        options = [(name, name) for name in registry.keys()]
        with Horizontal(classes="title-row"):
            yield CollapseToggle("▼", id="collapse", classes="collapse-toggle")
            yield Label(self._title, classes="panel-title")
            yield Label("", classes="panel-summary", markup=False)
            yield RemoveAction("Remove", id="remove", classes="remove-endpoint")
        with Vertical(id="body", classes="panel-body"):
            yield Select(
                options,
                prompt=f"Select {self._title.lower()}…",
                id="select",
                value=(self._default if self._default in dict(options) else Select.BLANK),
            )
            yield ScrollableContainer(id="fields")
        yield Static("", id="error", classes="error-msg")

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Rebuild config field widgets and post a Changed message when the converter selection changes."""
        if event.select.id != "select":
            return
        value = event.value
        self._converter_type = None if value is Select.BLANK else str(value)
        self.query_one(self._ERROR_WIDGET_ID, Static).update("")
        container = self.query_one("#fields", ScrollableContainer)
        await container.remove_children()
        if self._converter_type is not None:
            for widget in self._make_field_widgets(self._converter_type):
                await container.mount(widget)
        self.post_message(ConverterPanel.Changed(self, self._converter_type))

    def _make_field_widgets(self, converter_type: str) -> list:  # NOSONAR
        model = get_config_model(converter_type)
        widgets: list = []
        for name, fld in model.model_fields.items():
            if name in _NON_EDITABLE_FIELDS:
                continue
            required = fld.is_required()
            default = None if required else fld.get_default()
            field_type = _resolve_field_type(fld.annotation)
            prefix = "[red]*[/red] " if required else ""
            label_text = f"{prefix}{name}"
            if not required and default is not None:
                label_text += f" [dim](default: {default})[/dim]"
            widgets.append(Label(label_text, classes="field-label", markup=True))
            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                options = [(m.name, m.value) for m in field_type]
                if isinstance(default, enum.Enum):
                    select_value = default.value
                elif required or not options:
                    select_value = Select.BLANK
                else:
                    select_value = options[0][1]
                widgets.append(
                    Select(
                        options,
                        id=f"field-{self.id}-{name}",
                        allow_blank=required,
                        value=select_value,
                    )
                )
            else:
                field_input = Input(
                    value="" if default is None else str(default),
                    placeholder="required" if required else "",
                    id=f"field-{self.id}-{name}",
                )
                if name == "config_path":
                    widgets.append(Horizontal(field_input, Button("Browse", id="browse", classes="browse-path"), classes="path-row"))
                else:
                    widgets.append(field_input)
        return widgets

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the path picker for ``config_path`` with the selected converter's file or folder rules."""
        if event.button.id != "browse":
            return
        event.stop()
        converter = registry.get(self._converter_type) if self._converter_type else None
        if converter is None:
            return
        converter_class = type(converter)
        is_source = self._title.casefold().startswith("source")
        extensions: tuple[str, ...]
        if converter_class.uses_directory:
            mode, extensions = PickMode.FOLDER, ()
        elif is_source:
            mode, extensions = PickMode.OPEN_FILE, converter_class.get_source_extensions()
        else:
            mode, extensions = PickMode.SAVE_FILE, converter_class.get_destination_extensions()
        path_input = self.query_one(f"#field-{self.id}-config_path", Input)

        def _apply(path: str | None) -> None:
            """Put the picked path in the field; keep the current value when the picker is cancelled."""
            if path:
                path_input.value = path

        self.app.push_screen(PathPicker(f"Choose the {self._title} path", mode, path_input.value, extensions), _apply)

    def read_config(self) -> ConverterConfig:  # NOSONAR
        """Read current field values and return a validated config instance.

        Raises:
            ValidationError: if required fields are missing or invalid.
        """
        if self._converter_type is None:
            raise RuntimeError("No converter type selected")
        model = get_config_model(self._converter_type)
        config_dict: dict = {}
        for name, fld in model.model_fields.items():
            if name in _NON_EDITABLE_FIELDS:
                continue
            field_type = _resolve_field_type(fld.annotation)
            widget_id = f"#field-{self.id}-{name}"
            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                widget = self.query_one(widget_id, Select)
                if widget.value is not Select.BLANK:
                    config_dict[name] = field_type(widget.value)
            else:
                raw = self.query_one(widget_id, Input).value.strip()
                if raw:
                    target_type = (
                        fld.annotation.__origin__ if fld.annotation is not None and hasattr(fld.annotation, "__origin__") else fld.annotation
                    )
                    config_dict[name] = cast_value(raw, target_type)
        return model(**config_dict)

    def show_error(self, msg: str) -> None:
        """Display an error message in the panel's error Static widget."""
        self.query_one(self._ERROR_WIDGET_ID, Static).update(f"[red]{escape(msg)}[/red]")

    def clear_error(self) -> None:
        """Clear the panel's error Static widget."""
        self.query_one(self._ERROR_WIDGET_ID, Static).update("")
