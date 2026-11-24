"""Tests for the PySide6 GUI components.

Requires PySide6 (install with: pip install flync_converter[gui]).
Tests are skipped automatically when PySide6 is not installed.
The offscreen platform is used so no display server is required.
"""

import enum
import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

# Must be set before any Qt import so tests run headless in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication, QComboBox, QPushButton  # noqa: E402

from flync_converter.base import ConverterConfig  # noqa: E402
from flync_converter.base.base_converter import BaseConverter  # noqa: E402
from flync_converter.cli.gui.app import FlyncGUI  # noqa: E402
from flync_converter.cli.gui.widgets.converter_panel import ConverterPanel  # noqa: E402
from flync_converter.cli.gui.widgets.converter_panel_list import ConverterPanelList  # noqa: E402
from flync_converter.cli.gui.widgets.log_handler import LogWidgetHandler  # noqa: E402
from flync_converter.conversion_request import ConversionOutput, ConversionRequest, ConversionSource  # noqa: E402

# ---------------------------------------------------------------------------
# Session-scoped QApplication (pytest-qt provides qapp, but we also need it
# available for fixtures that don't use qtbot directly).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    return app


class _FakeJSONConverter(BaseConverter):
    """A BaseConverter-backed fake that exposes the picker metadata."""

    name = "json"
    uses_directory = False
    source_extensions = ("json",)
    destination_extensions = ("json",)

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


class _FakeYAMLConverter(BaseConverter):
    """A BaseConverter-backed fake exposing multiple source extensions."""

    name = "yaml"
    uses_directory = False
    source_extensions = ("yaml", "yml")
    destination_extensions = ("yaml",)

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


class _FakeFLYNCConverter(BaseConverter):
    """A BaseConverter-backed fake whose destinations are directories."""

    name = "flync"
    uses_directory = True

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


@pytest.fixture
def fake_registry():
    """Two minimal fake converters backed by real BaseConverter subclasses."""
    return {"json": _FakeJSONConverter(), "yaml": _FakeYAMLConverter()}


_PANEL_REGISTRY = "flync_converter.cli.gui.widgets.converter_panel.registry"
_APP_REGISTRY = "flync_converter.cli.gui.app.registry"
_UTILS_REGISTRY = "flync_converter.utils.registry"


def test_panel_initial_state(qapp_instance, fake_registry):
    """Panel has no converter selected on construction."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")
    assert panel.converter_type is None


def test_panel_default_selection(qapp_instance, fake_registry):
    """default= kwarg pre-selects the named converter."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
    assert panel.converter_type == "json"


def test_panel_builds_text_and_enum_fields(qapp_instance):
    """Typed config fields render as QLineEdit (text) or QComboBox (enum)."""
    from PySide6.QtWidgets import QLineEdit

    class Direction(enum.Enum):
        LEFT = "left"
        RIGHT = "right"

    class RichConfig(ConverterConfig):
        label: str
        direction: Direction = Direction.LEFT

    class RichConverter(MagicMock):
        def __init__(self, config: RichConfig = None):
            pass

    reg = {"rich": RichConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="rich")

    assert isinstance(panel._field_widgets["label"], QLineEdit)
    assert isinstance(panel._field_widgets["direction"], QComboBox)


def test_panel_enum_combo_contains_all_members(qapp_instance):
    """Enum QComboBox is populated with every member name."""

    class Color(enum.Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    class ColorConfig(ConverterConfig):
        color: Color = Color.RED

    class ColorConverter(MagicMock):
        def __init__(self, config: ColorConfig = None):
            pass

    reg = {"colorconv": ColorConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="colorconv")

    combo = panel._field_widgets["color"]
    assert isinstance(combo, QComboBox)
    names = [combo.itemText(i) for i in range(combo.count())]
    assert names == ["RED", "GREEN", "BLUE"]


def test_panel_config_path_renders_browse_button(qapp_instance, fake_registry):
    """The config_path field pairs the line edit with a Browse button."""
    from PySide6.QtWidgets import QLineEdit, QPushButton

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")

    line = panel._field_widgets["config_path"]
    found = [btn for btn in panel._fields_container.findChildren(QPushButton) if btn.text() == "Browse..."]
    assert isinstance(line, QLineEdit)
    assert found


def test_panel_source_browse_uses_open_dialog(qapp_instance, fake_registry):
    """The Source panel fills a file picked via QFileDialog.getOpenFileName."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getOpenFileName", return_value=("/tmp/in.json", "")) as get_open:
            panel._browse_path(line)

    assert line.text() == "/tmp/in.json"
    assert get_open.call_args[0][3] == "JSON files (*.json)"


def test_panel_destination_browse_uses_save_dialog(qapp_instance, fake_registry):
    """The Destination panel fills a file picked via QFileDialog.getSaveFileName."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Destination", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getSaveFileName", return_value=("/tmp/out.json", "")):
            panel._browse_path(line)

    assert line.text() == "/tmp/out.json"


def test_panel_browse_dialog_preseeded_from_line_edit(qapp_instance, fake_registry):
    """The picker starts in the directory of the current field text."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        line.setText("/work/current.json")
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as get_open:
            panel._browse_path(line)

    assert "/work" in get_open.call_args[0][2]


def test_panel_destination_flync_browse_uses_folder(qapp_instance):
    """FLYNC destinations use the native folder picker, not Save As."""
    from PySide6.QtWidgets import QFileDialog

    reg = {"flync": _FakeFLYNCConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Destination", default="flync")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getExistingDirectory", return_value="/work/dir") as get_dir:
            with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")) as get_save:
                panel._browse_path(line)

    assert line.text() == "/work/dir"
    get_dir.assert_called_once()
    get_save.assert_not_called()


def test_panel_source_browse_sets_name_filter(qapp_instance, fake_registry):
    """The source picker applies a single format-specific name filter."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as get_open:
            panel._browse_path(line)

    get_open.assert_called_once()
    assert get_open.call_args[0][3] == "JSON files (*.json)"


def test_panel_browse_is_noop_for_unregistered_converter(qapp_instance, fake_registry):
    """A converter with no registry entry does not open any dialog."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Destination", default="json")
        line = panel._field_widgets["config_path"]
        panel._converter_type = "csv"  # not in the registry
        with patch.object(QFileDialog, "getSaveFileName", return_value=("/tmp/x.csv", "")) as get_save:
            with patch.object(QFileDialog, "getExistingDirectory", return_value="/x"):
                panel._browse_path(line)

    get_save.assert_not_called()
    assert line.text() == ""


def test_panel_read_config_returns_instance(qapp_instance, fake_registry):
    """read_config() returns a ConverterConfig when a converter is selected."""
    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")

    panel._field_widgets["config_path"].setText("/some/path")
    cfg = panel.read_config()
    assert isinstance(cfg, ConverterConfig)


def _structured_registry():
    """A converter whose config holds a mapping and a sequence of models."""

    class SenderEcu(BaseModel):
        name: str

    class StructuredConfig(ConverterConfig):
        package_paths: dict[str, str] = Field(default_factory=dict)
        sender_ecus: list[SenderEcu] = Field(default_factory=list)

    class StructuredConverter(MagicMock):
        def __init__(self, config: StructuredConfig = None):
            pass

    return {"structured": StructuredConverter()}


def test_panel_structured_fields_default_to_json_text(qapp_instance):
    """Mapping and sequence defaults are shown as JSON text."""
    reg = _structured_registry()
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="structured")

    assert panel._field_widgets["package_paths"].text() == "{}"
    assert panel._field_widgets["sender_ecus"].text() == "[]"


def test_panel_read_config_parses_structured_json(qapp_instance):
    """JSON text entered in a structured field reaches the config as containers."""
    reg = _structured_registry()
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="structured")
        panel._field_widgets["config_path"].setText("/some/path")
        panel._field_widgets["package_paths"].setText('{"Frame": "Communication/Frames"}')
        panel._field_widgets["sender_ecus"].setText('[{"name": "ECU1"}]')
        cfg = panel.read_config()

    assert cfg.package_paths == {"Frame": "Communication/Frames"}
    assert [ecu.name for ecu in cfg.sender_ecus] == ["ECU1"]


def test_panel_read_config_rejects_invalid_structured_json(qapp_instance):
    """Invalid JSON is reported against the offending field."""
    reg = _structured_registry()
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="structured")
        panel._field_widgets["config_path"].setText("/some/path")
        panel._field_widgets["package_paths"].setText("{not json")

        with pytest.raises(ValueError, match="package_paths: invalid JSON"):
            panel.read_config()


def test_panel_read_config_raises_without_selection(qapp_instance, fake_registry):
    """read_config() raises RuntimeError when no converter type is selected."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    with pytest.raises(RuntimeError, match="No converter type selected"):
        panel.read_config()


def test_panel_show_and_clear_error(qapp_instance, fake_registry):
    """show_error() makes the label visible; clear_error() hides it."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    panel.show_error("something went wrong")
    assert not panel._error_label.isHidden()
    assert panel._error_label.text() == "something went wrong"

    panel.clear_error()
    assert panel._error_label.isHidden()


def test_panel_changed_signal_emitted_on_format_change(qapp_instance, fake_registry):
    """changed signal carries the new converter type string."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    received = []
    panel.changed.connect(received.append)

    idx = panel._format_combo.findData("json")
    panel._format_combo.setCurrentIndex(idx)

    assert received == ["json"]


def test_log_handler_routes_record_to_append_fn(qapp_instance):
    """LogWidgetHandler forwards formatted records to the supplied callable."""
    received: list[str] = []
    handler = LogWidgetHandler(received.append)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="hello gui",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert len(received) == 1
    assert "WARNING" in received[0]
    assert "hello gui" in received[0]


def test_gui_convert_button_initially_disabled(qapp_instance, fake_registry):
    """Convert button starts disabled until both panels have a selection."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        assert not window._convert_btn.isEnabled()
    finally:
        window.close()


def test_gui_convert_button_enabled_when_both_panels_selected(qapp_instance, fake_registry):
    """Convert button enables once source and destination are both set."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        window._source_panels.panels[0]._converter_type = "json"
        window._dest_panels.panels[0]._converter_type = "yaml"
        window._refresh_convert_button()
        assert window._convert_btn.isEnabled()
    finally:
        window.close()


def test_gui_convert_button_follows_the_format_selection(qapp_instance, fake_registry):
    """Choosing and clearing a format in the dropdown enables and disables Convert."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()
        try:
            source, destination = window._source_panels.panels[0], window._dest_panels.panels[0]
            source._format_combo.setCurrentIndex(source._format_combo.findData("json"))
            destination._format_combo.setCurrentIndex(destination._format_combo.findData("yaml"))
            assert window._convert_btn.isEnabled()

            window._dest_panels.add_panel()
            assert not window._convert_btn.isEnabled()

            window._dest_panels.remove_panel(window._dest_panels.panels[1])
            assert window._convert_btn.isEnabled()

            source._format_combo.setCurrentIndex(0)
            assert not window._convert_btn.isEnabled()
        finally:
            window.close()


def test_gui_source_error_shown_on_bad_source_config(qapp_instance, fake_registry):
    """If source read_config raises, the error is shown on the source panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Neither panel has a selection — source read_config raises first.
        window._on_convert_clicked()
        assert not window._source_panels.panels[0]._error_label.isHidden()
    finally:
        window.close()


def test_gui_dest_error_shown_on_bad_dest_config(qapp_instance, fake_registry):
    """If dest read_config raises, the error is shown on the destination panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Source is valid, dest has no selection.
        window._source_panels.panels[0]._converter_type = "json"
        with patch.object(
            window._source_panels.panels[0],
            "read_config",
            return_value=ConverterConfig(config_path="/tmp"),
        ):
            window._on_convert_clicked()
        assert not window._dest_panels.panels[0]._error_label.isHidden()
    finally:
        window.close()


def test_gui_conversion_runs_in_background(qapp_instance, fake_registry):
    """The conversion runs off the main thread with the complete request."""
    import threading
    import time

    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        source_cfg = ConverterConfig(config_path="/tmp/source")
        dest_cfg = ConverterConfig(config_path="/tmp/destination")
        request = ConversionRequest(
            sources=[ConversionSource(path=source_cfg.config_path, converter_type="json", config=source_cfg)],
            outputs=[ConversionOutput(path=dest_cfg.config_path, converter_type="yaml", config=dest_cfg)],
        )

        with patch("flync_converter.cli.gui.app.Converter.convert_request") as convert_request:
            window._run_conversion(request, [], [])

            # Wait for the background thread to finish (max 2 s).
            deadline = time.monotonic() + 2.0
            while threading.active_count() > 1 and time.monotonic() < deadline:
                time.sleep(0.05)

            convert_request.assert_called_once_with(request)
    finally:
        window.close()


def test_panel_list_add_remove_and_renumber(qapp_instance, fake_registry):
    """Any endpoint can be removed while one endpoint of the same role remains."""
    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel_list = ConverterPanelList("Source", default="json")
    try:
        first = panel_list.panels[0]
        first_frame = panel_list._entries[0][0]
        initial_size_hint = first_frame.sizeHint()
        second = panel_list.add_panel()
        assert first_frame.sizeHint() == initial_size_hint
        third = panel_list.add_panel()
        assert first_frame.sizeHint() == initial_size_hint
        assert [panel._title for panel in panel_list.panels] == ["Source 1", "Source 2", "Source 3"]
        remove_button = panel_list._entries[0][2]
        browse_button = next(button for button in first.findChildren(QPushButton) if button.text() == "Browse...")
        assert remove_button.width() == browse_button.width()
        assert panel_list._panels_layout.indexOf(panel_list._add_button) == len(panel_list.panels)

        assert panel_list.remove_panel(first)
        assert panel_list.panels == [second, third]
        assert [panel._title for panel in panel_list.panels] == ["Source 1", "Source 2"]

        assert panel_list.remove_panel(second)
        assert panel_list.panels == [third]
        assert not panel_list.remove_panel(third)
    finally:
        panel_list.close()


def test_gui_builds_many_to_many_request(qapp_instance, fake_registry):
    """All configured panels are preserved in order in one ConversionRequest."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()
    try:
        source_two = window._source_panels.add_panel()
        destination_two = window._dest_panels.add_panel()
        source_configs = [
            ConverterConfig(config_path="/tmp/source-1"),
            ConverterConfig(config_path="/tmp/source-2"),
        ]
        destination_configs = [
            ConverterConfig(config_path="/tmp/output-1"),
            ConverterConfig(config_path="/tmp/output-2"),
        ]
        for panel, config, converter_type in zip(window._source_panels.panels, source_configs, ["json", "yaml"]):
            panel._converter_type = converter_type
            panel.read_config = MagicMock(return_value=config)
        for panel, config, converter_type in zip(window._dest_panels.panels, destination_configs, ["yaml", "json"]):
            panel._converter_type = converter_type
            panel.read_config = MagicMock(return_value=config)

        with patch.object(window, "_run_conversion") as run_conversion:
            window._on_convert_clicked()

        request = run_conversion.call_args.args[0]
        assert [str(source.path) for source in request.sources] == ["/tmp/source-1", "/tmp/source-2"]
        assert [source.converter_type for source in request.sources] == ["json", "yaml"]
        assert [str(output.path) for output in request.outputs] == ["/tmp/output-1", "/tmp/output-2"]
        assert [output.converter_type for output in request.outputs] == ["yaml", "json"]
        assert source_two in window._source_panels.panels
        assert destination_two in window._dest_panels.panels
    finally:
        window.close()


def test_gui_source_destination_overlap_shows_error(qapp_instance, fake_registry):
    """A request whose source and destination paths overlap surfaces an inline error."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()
    try:
        shared = "/tmp/shared/path"
        for panel in [*window._source_panels.panels, *window._dest_panels.panels]:
            panel._converter_type = "json"
            panel.read_config = MagicMock(return_value=ConverterConfig(config_path=shared))

        with patch.object(window, "_run_conversion") as run_conversion:
            window._on_convert_clicked()

        run_conversion.assert_not_called()
        assert all(not panel._error_label.isHidden() for panel in window._source_panels.panels)
        assert all(not panel._error_label.isHidden() for panel in window._dest_panels.panels)
    finally:
        window.close()


def test_force_exit_on_sigint_exits_with_130():
    """Ctrl+C exits the GUI process with status 130."""
    import flync_converter.cli.gui.app as gui_app

    with patch("flync_converter.cli.gui.app.os._exit") as mock_exit:
        gui_app._force_exit_on_sigint(2, None)

    mock_exit.assert_called_once_with(130)


def test_install_sigint_handler_sets_handler_and_starts_timer(qapp_instance):
    """The SIGINT handler is installed and a timer keeps Python signal handling running."""
    import signal

    import flync_converter.cli.gui.app as gui_app

    previous = signal.getsignal(signal.SIGINT)
    try:
        timer = gui_app._install_sigint_handler(qapp_instance)
        assert signal.getsignal(signal.SIGINT) is gui_app._force_exit_on_sigint
        assert timer.isActive()
        assert timer.interval() == gui_app._SIGNAL_POLL_INTERVAL_MS
        assert timer.parent() is qapp_instance
    finally:
        signal.signal(signal.SIGINT, previous)
        timer.stop()
        timer.deleteLater()


def test_run_gui_installs_sigint_handler(qapp_instance):
    """run_gui installs the Ctrl+C handler before entering the event loop."""
    import flync_converter.cli.gui.app as gui_app

    with (
        patch.object(gui_app, "registry"),
        patch.object(gui_app, "FlyncGUI"),
        patch.object(gui_app, "_install_sigint_handler") as mock_install,
        patch.object(qapp_instance, "exec", return_value=0),
        pytest.raises(SystemExit),
    ):
        gui_app.run_gui()

    mock_install.assert_called_once_with(qapp_instance)


def test_panel_collapse_hides_the_form_and_keeps_values(qapp_instance, fake_registry):
    """A collapsed panel shows a summary of its endpoint and keeps its field values."""
    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        panel._field_widgets["config_path"].setText("/tmp/in")

        panel._collapse_button.click()

        assert panel.is_collapsed
        assert panel._body.isHidden()
        assert panel._summary_label.text() == "json · /tmp/in"
        panel.show_error("bad")
        assert not panel._error_label.isHidden()

        panel._collapse_button.click()

        assert not panel.is_collapsed
        assert panel._summary_label.isHidden()
        assert str(panel.read_config().config_path) == "/tmp/in"
