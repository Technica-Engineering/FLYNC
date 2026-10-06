"""ConverterPanel widget — format selector + dynamic config form (PySide6)."""

from __future__ import annotations

import enum
import os
import typing
from typing import Optional, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flync_converter.base import ConverterConfig
from flync_converter.registry import registry
from flync_converter.utils import cast_value, get_config_model


def _resolve_field_type(annotation):
    """Unwrap Optional/Union and return the inner type."""
    origin = getattr(annotation, "__origin__", None)
    if origin is Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return args[0] if args else annotation
    return annotation


#: Config fields managed by the stored configuration file or elsewhere, not edited in the panel.
_NON_EDITABLE_FIELDS = frozenset({"version", "report_enabled", "report_min_log_level", "persist_config"})


class ConverterPanel(QWidget):
    """One half of the split panel: format selector + dynamic config form."""

    changed = Signal(object)  # emits converter_type str or None

    def __init__(self, title: str, default: Optional[str] = None, parent=None) -> None:
        """Initialize the converter panel.

        Args:
            title: Title label for the panel (e.g., "Source" or "Destination").
            default: Optional default converter to select.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._title = title
        self._default = default
        self._converter_type: Optional[str] = None
        self._field_widgets: dict[str, QWidget] = {}
        self._setup_ui()

        if default:
            idx = self._format_combo.findData(default)
            if idx >= 0:
                self._format_combo.setCurrentIndex(idx)

    def _setup_ui(self) -> None:
        """Set up the panel UI with format selector and config form."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_label = QLabel(self._title)
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        title_label.setFont(font)
        layout.addWidget(title_label)

        self._format_combo = QComboBox()
        self._format_combo.addItem(f"Select {self._title.lower()}…", None)
        for name in registry.keys():
            self._format_combo.addItem(name, name)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._format_combo.setSizePolicy(
            self._format_combo.sizePolicy().horizontalPolicy(),
            self._format_combo.sizePolicy().verticalPolicy(),
        )
        layout.addWidget(self._format_combo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._fields_layout.setSpacing(4)
        scroll.setWidget(self._fields_container)
        layout.addWidget(scroll, stretch=1)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #cc3333;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

    @property
    def converter_type(self) -> Optional[str]:
        """Return the currently selected converter type name, or None if none is selected."""
        return self._converter_type

    def _on_format_changed(self, index: int) -> None:
        self._converter_type = self._format_combo.itemData(index)
        self._clear_fields()
        self.clear_error()
        if self._converter_type:
            self._build_fields(self._converter_type)
        self.changed.emit(self._converter_type)

    def _clear_fields(self) -> None:
        self._field_widgets.clear()
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()  # type: ignore[union-attr]

    def _build_fields(self, converter_type: str) -> None:  # NOSONAR
        model = get_config_model(converter_type)
        for name, fld in model.model_fields.items():
            if name in _NON_EDITABLE_FIELDS:
                continue

            required = fld.is_required()
            default = None if required else fld.get_default()
            field_type = _resolve_field_type(fld.annotation)

            label_text = f"{'* ' if required else ''}{name}"
            if not required and default is not None:
                label_text += f"  (default: {default})"
            label = QLabel(label_text)
            if required:
                label.setStyleSheet("color: #cc3333; font-weight: bold;")
            else:
                label.setStyleSheet("color: #888888;")
            self._fields_layout.addWidget(label)

            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                combo = QComboBox()
                for member in field_type:
                    combo.addItem(member.name, member.value)
                if isinstance(default, enum.Enum):
                    idx = combo.findData(default.value)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                self._fields_layout.addWidget(combo)
                self._field_widgets[name] = combo
            else:
                line = QLineEdit()
                if default is not None:
                    line.setText(str(default))
                if required:
                    line.setPlaceholderText("required")
                if name == "config_path":
                    self._add_path_field(line)
                else:
                    self._fields_layout.addWidget(line)
                self._field_widgets[name] = line

    def _add_path_field(self, line_edit: QLineEdit) -> None:
        """Add one Browse button with automatic file/folder behavior."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(line_edit, stretch=1)

        browse = QPushButton("Browse...")
        browse.clicked.connect(lambda _checked=False, le=line_edit: self._browse_path(le))
        row.addWidget(browse)

        container = QWidget()
        container.setContentsMargins(0, 0, 0, 0)
        container.setLayout(row)
        container.setSizePolicy(
            self._format_combo.sizePolicy().horizontalPolicy(),
            container.sizePolicy().verticalPolicy(),
        )
        self._fields_layout.addWidget(container)

    @property
    def _is_source(self) -> bool:
        return self._title.casefold() == "source"

    @staticmethod
    def _initial_directory(line_edit: QLineEdit) -> str:
        current = line_edit.text().strip()
        if not current:
            return ""
        if os.path.isdir(current):
            return current
        return os.path.dirname(current)

    def _browse_path(self, line_edit: QLineEdit) -> None:
        """Open a picker using metadata from the selected converter."""
        converter = registry.get(self._converter_type) if self._converter_type else None
        if converter is None:
            return

        converter_class = type(converter)
        if converter_class.uses_directory:
            self._browse_folder(line_edit)
            return

        extensions = converter_class.get_source_extensions() if self._is_source else converter_class.get_destination_extensions()
        file_filter = converter_class.build_file_filter(extensions)

        if self._is_source:
            self._browse_source_file(line_edit, file_filter)
            return

        self._browse_destination_file(line_edit, extensions, file_filter)

    def _browse_source_file(
        self,
        line_edit: QLineEdit,
        file_filter: str,
    ) -> None:
        """Select a source file and update the input field."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose source file",
            line_edit.text().strip() or self._initial_directory(line_edit),
            file_filter,
        )
        if path:
            line_edit.setText(path)

    def _browse_destination_file(
        self,
        line_edit: QLineEdit,
        extensions: tuple[str, ...],
        file_filter: str,
    ) -> None:
        """Select a destination file and update the input field."""
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save destination",
            line_edit.text().strip() or self._initial_directory(line_edit),
            file_filter,
        )
        if path:
            line_edit.setText(self._append_destination_extension(path, extensions))

    @staticmethod
    def _append_destination_extension(
        path: str,
        extensions: tuple[str, ...],
    ) -> str:
        """Append the default converter extension when the path has none."""
        if os.path.splitext(path)[1] or not extensions:
            return path
        return f"{path}.{extensions[0].lstrip('.')}"

    def _browse_folder(self, line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            f"Choose {self._title.lower()} folder",
            self._initial_directory(line_edit),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            line_edit.setText(path)

    def read_config(self) -> ConverterConfig:  # NOSONAR
        """Read current field values and return a validated config instance.

        Raises:
            RuntimeError: if no converter type is selected.
            ValidationError: if required fields are missing or invalid.
        """
        if self._converter_type is None:
            raise RuntimeError("No converter type selected")
        model = get_config_model(self._converter_type)
        config_dict: dict = {}
        for name, fld in model.model_fields.items():
            field_type = _resolve_field_type(fld.annotation)
            widget = self._field_widgets.get(name)
            if widget is None:
                continue
            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                value = widget.currentData()  # type: ignore[attr-defined]
                if value is not None:
                    config_dict[name] = field_type(value)
            else:
                raw = widget.text().strip()  # type: ignore[attr-defined]
                if raw:
                    target_type = (
                        fld.annotation.__origin__ if fld.annotation is not None and hasattr(fld.annotation, "__origin__") else fld.annotation
                    )
                    config_dict[name] = cast_value(raw, target_type)
        return model(**config_dict)

    def show_error(self, msg: str) -> None:
        """Display an error message in the panel's error label."""
        self._error_label.setText(msg)
        self._error_label.show()

    def clear_error(self) -> None:
        """Hide and clear the panel's error label."""
        self._error_label.clear()
        self._error_label.hide()
