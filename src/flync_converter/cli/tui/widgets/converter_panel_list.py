"""Ordered collection of converter panels for the Textual TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button

from .converter_panel import ConverterPanel, RemoveAction


class ConverterPanelList(VerticalScroll):
    """Manage a non-empty ordered collection of source or destination panels."""

    DEFAULT_CSS = """
    ConverterPanelList {
        width: 1fr;
        height: 1fr;
        margin: 0;
        padding: 0 0 0 1;
        scrollbar-size: 1 1;
        scrollbar-gutter: stable;
        overflow-x: hidden;
    }

    ConverterPanelList > ConverterPanel {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    ConverterPanelList > .add-row {
        width: 100%;
        height: 3;
        padding: 0 1;
        dock: bottom;
        background: $surface;
    }

    ConverterPanelList .add-endpoint {
        width: 100%;
        height: 3;
        margin: 0;
        border: solid $primary-background-lighten-2;
    }
    """

    class Changed(Message):
        """Posted after an endpoint is added or removed."""

    def __init__(self, role: str, default: str = "flync", **kwargs) -> None:
        super().__init__(**kwargs)
        self._role = role
        self._role_key = role.casefold()
        self._default = default
        self._next_index = 1

    @property
    def panels(self) -> list[ConverterPanel]:
        """Return endpoint panels in visible order."""
        return list(self.query(ConverterPanel))

    def compose(self) -> ComposeResult:
        yield self._new_panel()
        with Horizontal(id=f"add-{self._role_key}-row", classes="add-row"):
            yield Button(f"Add {self._role}", id=f"add-{self._role_key}", classes="add-endpoint")

    def _new_panel(self) -> ConverterPanel:
        """Return a new panel with an ID that stays unique after removals."""
        index = self._next_index
        self._next_index += 1
        return ConverterPanel(f"{self._role} {index}", default=self._default, removable=index > 1, id=f"{self._role_key}-panel-{index}")

    async def add_panel(self) -> ConverterPanel:
        """Insert a new endpoint directly before the Add button."""
        panel = self._new_panel()
        add_row = self.query_one(f"#add-{self._role_key}-row", Horizontal)
        add_button = self.query_one(f"#add-{self._role_key}", Button)
        await self.mount(panel, before=add_row)
        self._refresh_entries()
        panel.scroll_visible()
        add_button.focus()
        self.post_message(self.Changed())
        return panel

    async def remove_panel(self, panel: ConverterPanel) -> bool:
        """Remove an endpoint while preserving at least one endpoint of the role."""
        panels = self.panels
        if len(panels) == 1 or panel not in panels:
            return False
        index = panels.index(panel)
        await panel.remove()
        self._refresh_entries()
        remaining = self.panels
        neighbour = remaining[min(index, len(remaining) - 1)]
        neighbour.query_one("#collapse" if neighbour.is_collapsed else "#select").focus()
        self.post_message(self.Changed())
        return True

    async def on_remove_action_pressed(self, event: RemoveAction.Pressed) -> None:
        """Remove the endpoint that owns the activated Remove action."""
        event.stop()
        await self.remove_panel(event.action.query_ancestor(ConverterPanel))

    def _refresh_entries(self) -> None:
        """Renumber titles and update Remove button availability."""
        panels = self.panels
        removable = len(panels) > 1
        for index, panel in enumerate(panels, start=1):
            panel.set_title(f"{self._role} {index}")
            panel.set_remove_enabled(removable)
