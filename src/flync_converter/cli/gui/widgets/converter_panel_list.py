"""Collection widget for managing multiple converter endpoint panels."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .converter_panel import ConverterPanel


class ConverterPanelList(QWidget):
    """Manage an ordered, non-empty collection of source or destination panels."""

    changed = Signal()

    def __init__(self, role: str, default: str = "flync", parent=None) -> None:
        super().__init__(parent)
        self._role = role
        self._default = default
        self._entries: list[tuple[QFrame, ConverterPanel, QPushButton]] = []
        self._setup_ui()
        self.add_panel()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._panels_layout = QVBoxLayout(self._container)
        self._panels_layout.setContentsMargins(0, 0, 0, 0)
        self._panels_layout.setSpacing(8)

        self._add_button = QPushButton(f"Add {self._role}")
        self._add_button.clicked.connect(self.add_panel)
        self._panels_layout.addWidget(self._add_button)
        self._panels_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, stretch=1)

    @property
    def panels(self) -> list[ConverterPanel]:
        """Return endpoint panels in their visible order."""
        return [panel for _, panel, _ in self._entries]

    def add_panel(self) -> ConverterPanel:
        """Append and return a new endpoint panel."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        entry_layout = QVBoxLayout(frame)
        entry_layout.setContentsMargins(4, 4, 4, 4)

        panel = ConverterPanel(self._role, default=self._default)
        panel.changed.connect(lambda _converter_type: self.changed.emit())
        remove_button = QPushButton("Remove")
        panel.set_title_action(remove_button)
        entry_layout.addWidget(panel)
        remove_button.clicked.connect(lambda _checked=False, item=panel: self.remove_panel(item))

        self._entries.append((frame, panel, remove_button))
        self._panels_layout.insertWidget(self._panels_layout.count() - 2, frame)
        self._refresh_entries()
        self.changed.emit()
        return panel

    def remove_panel(self, panel: ConverterPanel) -> bool:
        """Remove a panel when another endpoint of the same role remains."""
        if len(self._entries) == 1:
            return False
        for index, (frame, candidate, _button) in enumerate(self._entries):
            if candidate is panel:
                self._entries.pop(index)
                self._panels_layout.removeWidget(frame)
                frame.deleteLater()
                self._refresh_entries()
                self.changed.emit()
                return True
        return False

    def _refresh_entries(self) -> None:
        """Renumber panels and prevent removing the final endpoint."""
        removable = len(self._entries) > 1
        for index, (_frame, panel, remove_button) in enumerate(self._entries, start=1):
            panel.set_title(f"{self._role} {index}")
            remove_button.setEnabled(removable)
