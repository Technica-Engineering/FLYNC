"""FlyncTUI Textual application and entry point."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from typing import Optional

from pydantic import ValidationError
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.events import Resize
from textual.widgets import Button, Footer, Header, Log, Select, Static

from flync_converter import Converter
from flync_converter.base import ConverterConfig
from flync_converter.cli.dynamic import DST_PREFIX, SRC_PREFIX
from flync_converter.cli.preview import ConversionEndpoint, config_endpoint, conversion_summary, render_preview
from flync_converter.conversion_request import ConversionOutput, ConversionRequest, ConversionSource
from flync_converter.registry import registry

from .widgets import ConverterPanel, ConverterPanelList, LogWidgetHandler

_SOURCE_PANELS_ID = "source-panels"
_DESTINATION_PANELS_ID = "destination-panels"
_CONVERT_BUTTON_ID = "btn-convert"
_RUN_LOG_ID = "run-log"
_SOURCE_PANELS = f"#{_SOURCE_PANELS_ID}"
_DESTINATION_PANELS = f"#{_DESTINATION_PANELS_ID}"
_CONVERT_BUTTON = f"#{_CONVERT_BUTTON_ID}"
_RUN_LOG = f"#{_RUN_LOG_ID}"
_ADD_PANEL_TARGETS = {
    "add-source": _SOURCE_PANELS,
    "add-destination": _DESTINATION_PANELS,
}

_CSS = """
Screen {
    background: $surface;
}

#panels {
    height: 1fr;
    min-height: 0;
    margin: 0 1;
    padding: 0;
}

#source-panels,
#destination-panels {
    width: 1fr;
    height: 1fr;
    margin: 0;
}

#source-panels {
    margin-right: 1;
}

#destination-panels {
    margin-left: 1;
}

#run-log {
    height: 6;
    border: solid $accent;
    margin: 1 1 0 1;
    padding: 0 1;
}

#btn-row {
    height: 4;
    padding: 0 1;
    align: left middle;
}

#log-level-select {
    width: 18;
    margin: 0;
}

#btn-row-spacer {
    width: 1fr;
}

#btn-convert {
    width: 18;
    margin: 0;
}
"""


class FlyncTUI(App):
    """flync Converter — interactive TUI (single-screen split-panel)."""

    TITLE = "flync Converter"
    SUB_TITLE = "Interactive format conversion"
    CSS = _CSS
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._no_preview = False
        self._log_handler: Optional[LogWidgetHandler] = None
        self._converting = False

    _LOG_LEVELS = [
        ("DEBUG", "DEBUG"),
        ("INFO", "INFO"),
        ("WARNING", "WARNING"),
        ("ERROR", "ERROR"),
    ]
    _DEFAULT_LOG_LEVEL = "WARNING"
    _LOG_MIN_HEIGHT = 3
    _LOG_MAX_HEIGHT = 6
    #: Terminal rows kept for the rest of the screen before the log grows past its minimum.
    _LOG_RESERVED_HEIGHT = 25

    def on_mount(self) -> None:
        """Attach a log handler that routes Python log records to the on-screen Log widget."""
        handler = LogWidgetHandler(self.query_one(_RUN_LOG, Log))
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handler.setLevel(self._DEFAULT_LOG_LEVEL)
        logging.getLogger().setLevel(self._DEFAULT_LOG_LEVEL)
        logging.getLogger().addHandler(handler)
        self._log_handler = handler
        self._apply_log_height(self.size.height)

    def on_resize(self, event: Resize) -> None:
        """Keep the log compact enough for the endpoint columns at small terminal sizes."""
        self._apply_log_height(event.size.height)

    def _apply_log_height(self, terminal_height: int) -> None:
        """Shrink the log on short terminals; the endpoint columns take the remaining rows."""
        try:
            log = self.query_one(_RUN_LOG, Log)
        except NoMatches:
            return
        log.styles.height = max(self._LOG_MIN_HEIGHT, min(self._LOG_MAX_HEIGHT, terminal_height - self._LOG_RESERVED_HEIGHT))

    def on_unmount(self) -> None:
        """Remove the log handler when the TUI app exits."""
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

    def compose(self) -> ComposeResult:  # NOSONAR
        """Build the TUI layout: source/dest converter panels, log output, and control buttons."""
        yield Header()
        with Horizontal(id="panels"):
            yield ConverterPanelList("Source", default="flync", id=_SOURCE_PANELS_ID)
            yield ConverterPanelList("Destination", default="flync", id=_DESTINATION_PANELS_ID)
        yield Log(highlight=True, id=_RUN_LOG_ID)
        with Horizontal(id="btn-row"):
            yield Select(
                self._LOG_LEVELS,
                id="log-level-select",
                allow_blank=False,
                value=self._DEFAULT_LOG_LEVEL,
            )
            yield Static("", id="btn-row-spacer")
            yield Button("Convert", id=_CONVERT_BUTTON_ID, variant="primary", disabled=True)
        yield Footer()

    # ------------------------------------------------------------------
    # Panel events
    # ------------------------------------------------------------------

    def on_converter_panel_changed(self, event: ConverterPanel.Changed) -> None:
        """Re-evaluate whether the Convert button should be enabled when a panel selection changes."""
        self._refresh_convert_button()

    def on_converter_panel_list_changed(self, event: ConverterPanelList.Changed) -> None:
        """Refresh conversion availability after adding or removing an endpoint."""
        self._refresh_convert_button()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update the active log level when the log-level selector changes."""
        if event.select.id == "log-level-select" and event.value is not Select.BLANK:
            level = str(event.value)
            logging.getLogger().setLevel(level)
            if self._log_handler is not None:
                self._log_handler.setLevel(level)

    def _refresh_convert_button(self) -> None:
        try:
            sources = self.query_one(_SOURCE_PANELS, ConverterPanelList).panels
            destinations = self.query_one(_DESTINATION_PANELS, ConverterPanelList).panels
            btn = self.query_one(_CONVERT_BUTTON, Button)
        except NoMatches:
            return
        panels = [*sources, *destinations]
        btn.disabled = self._converting or not panels or not all(panel.converter_type for panel in panels)

    def get_system_commands(self, screen) -> Iterable[SystemCommand]:
        """Expose the preview toggle in the Textual command palette (Ctrl+P)."""
        yield from super().get_system_commands(screen)
        if self._no_preview:  # preview currently hidden
            title = "Preview conversion: Enable"
            help_text = "Start showing the conversion preview before converting"
        else:  # preview currently shown
            title = "Preview conversion: Disable"
            help_text = "Stop showing the conversion preview before converting"
        yield SystemCommand(title, help_text, self.action_toggle_preview)

    def action_toggle_preview(self) -> None:
        """Flip whether the conversion preview is shown before converting."""
        self._no_preview = not self._no_preview

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle endpoint management and execute the complete conversion request."""
        button_id = event.button.id or ""
        panel_selector = _ADD_PANEL_TARGETS.get(button_id)
        if panel_selector is not None:
            await self.query_one(panel_selector, ConverterPanelList).add_panel()
        elif button_id == _CONVERT_BUTTON_ID:
            self._convert_clicked()

    def _convert_clicked(self) -> None:
        """Validate every endpoint and start the requested conversion."""
        source_panels = self.query_one(_SOURCE_PANELS, ConverterPanelList).panels
        destination_panels = self.query_one(_DESTINATION_PANELS, ConverterPanelList).panels
        configured_sources = self._read_panels(source_panels)
        if configured_sources is None:
            return
        configured_destinations = self._read_panels(destination_panels)
        if configured_destinations is None:
            return

        try:
            request = ConversionRequest(
                sources=[
                    ConversionSource(path=config.config_path, converter_type=converter_type, config=config)
                    for converter_type, config in configured_sources
                ],
                outputs=[
                    ConversionOutput(path=config.config_path, converter_type=converter_type, config=config)
                    for converter_type, config in configured_destinations
                ],
            )
        except ValidationError as exc:
            for panel in [*source_panels, *destination_panels]:
                panel.show_error(str(exc))
            return
        self._run_conversion(
            request,
            [config_endpoint(converter_type, config, SRC_PREFIX) for converter_type, config in configured_sources],
            [config_endpoint(converter_type, config, DST_PREFIX) for converter_type, config in configured_destinations],
        )

    @staticmethod
    def _read_panels(panels: list[ConverterPanel]) -> list[tuple[str, ConverterConfig]] | None:
        """Validate every panel and return its converter type and configuration."""
        configured: list[tuple[str, ConverterConfig]] = []
        for panel in panels:
            converter_type = panel.converter_type
            if converter_type is None:
                panel.show_error("Select a format for every endpoint before converting.")
                panel.scroll_visible()
                return None
            try:
                config = panel.read_config()
                panel.clear_error()
            except Exception as exc:
                panel.show_error(str(exc))
                panel.scroll_visible()
                return None
            configured.append((converter_type, config))
        return configured

    def _run_conversion(
        self,
        request: ConversionRequest,
        sources: list[ConversionEndpoint],
        destinations: list[ConversionEndpoint],
    ) -> None:
        """Print the preview of ``request`` and run it in a background thread.

        Args:
            request: The conversion to run.
            sources: The source endpoints of the preview, in merge order.
            destinations: The destination endpoints of the preview.
        """
        log = self.query_one(_RUN_LOG, Log)
        btn = self.query_one(_CONVERT_BUTTON, Button)
        self._converting = True
        btn.disabled = True
        log.clear()
        if not self._no_preview:
            log.write_lines(render_preview(sources, destinations).splitlines())
        log.write_line(conversion_summary(sources, destinations))

        def _worker() -> None:
            """Run the N-to-N request in a background thread and report its result."""
            try:
                Converter.convert_request(request)
                self._post_from_worker(log.write_line, "Conversion completed successfully.")
            except Exception as exc:
                self._post_from_worker(log.write_line, f"Conversion failed: {exc}")
            finally:
                self._post_from_worker(self._conversion_finished)

        threading.Thread(target=_worker, daemon=True).start()

    def _conversion_finished(self) -> None:
        """Allow the next conversion once the running one has ended."""
        self._converting = False
        self._refresh_convert_button()

    def _post_from_worker(self, callback, *args) -> None:
        """Run ``callback`` on the app's event loop from a worker thread, unless the app is already gone.

        The conversion thread can outlive the app (the user quits mid-conversion); calling
        ``call_from_thread`` then raises ``RuntimeError: Event loop is closed``, and there is
        nothing left to update, so the call is dropped.
        """
        if not self.is_running:
            return
        try:
            self.call_from_thread(callback, *args)
        except RuntimeError:
            pass


def run_tui() -> None:
    """Load plugins and launch the Textual TUI."""
    registry.load_plugins()
    FlyncTUI().run()
