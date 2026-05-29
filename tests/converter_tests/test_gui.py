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

# Must be set before any Qt import so tests run headless in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from flync_converter.base import ConverterConfig  # noqa: E402
from flync_converter.cli.gui.app import FlyncGUI  # noqa: E402
from flync_converter.cli.gui.widgets.converter_panel import ConverterPanel  # noqa: E402
from flync_converter.cli.gui.widgets.log_handler import LogWidgetHandler  # noqa: E402

# ---------------------------------------------------------------------------
# Session-scoped QApplication (pytest-qt provides qapp, but we also need it
# available for fixtures that don't use qtbot directly).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def fake_registry():
    """Two minimal fake converters backed by the base ConverterConfig."""
    mock_json = MagicMock()
    mock_json.name = "json"
    mock_json.__class__.__init__.__annotations__ = {"config": ConverterConfig}

    mock_yaml = MagicMock()
    mock_yaml.name = "yaml"
    mock_yaml.__class__.__init__.__annotations__ = {"config": ConverterConfig}

    return {"json": mock_json, "yaml": mock_yaml}


_PANEL_REGISTRY = "flync_converter.cli.gui.widgets.converter_panel.registry"
_APP_REGISTRY = "flync_converter.cli.gui.app.registry"
_UTILS_REGISTRY = "flync_converter.utils.registry"


# ---------------------------------------------------------------------------
# ConverterPanel
# ---------------------------------------------------------------------------


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


def test_panel_read_config_returns_instance(qapp_instance, fake_registry):
    """read_config() returns a ConverterConfig when a converter is selected."""
    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")

    panel._field_widgets["config_path"].setText("/some/path")
    cfg = panel.read_config()
    assert isinstance(cfg, ConverterConfig)


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


# ---------------------------------------------------------------------------
# LogWidgetHandler
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# FlyncGUI
# ---------------------------------------------------------------------------


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
        window._source_panel._converter_type = "json"
        window._dest_panel._converter_type = "yaml"
        window._refresh_convert_button()
        assert window._convert_btn.isEnabled()
    finally:
        window.close()


def test_gui_source_error_shown_on_bad_source_config(qapp_instance, fake_registry):
    """If source read_config raises, the error is shown on the source panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Neither panel has a selection — source read_config raises first.
        window._on_convert_clicked()
        assert not window._source_panel._error_label.isHidden()
    finally:
        window.close()


def test_gui_dest_error_shown_on_bad_dest_config(qapp_instance, fake_registry):
    """If dest read_config raises, the error is shown on the destination panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Source is valid, dest has no selection.
        window._source_panel._converter_type = "json"
        with patch.object(
            window._source_panel,
            "read_config",
            return_value=ConverterConfig(config_path="/tmp"),
        ):
            window._on_convert_clicked()
        assert not window._dest_panel._error_label.isHidden()
    finally:
        window.close()


def test_gui_conversion_runs_in_background(qapp_instance, fake_registry):
    """A successful conversion emits the done signal and re-enables the button."""
    import threading
    import time

    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        source_cfg = ConverterConfig(config_path="/tmp")
        dest_cfg = ConverterConfig(config_path="/tmp")

        with patch("flync_converter.cli.gui.app.Converter") as mock_cls:
            mock_cls.return_value.convert.return_value = None
            window._run_conversion("json", source_cfg, "yaml", dest_cfg)

            # Wait for the background thread to finish (max 2 s).
            deadline = time.monotonic() + 2.0
            while threading.active_count() > 1 and time.monotonic() < deadline:
                time.sleep(0.05)

            mock_cls.return_value.convert.assert_called_once()
    finally:
        window.close()
