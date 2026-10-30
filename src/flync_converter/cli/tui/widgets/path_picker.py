"""Modal file and folder picker for the ``config_path`` field of a converter panel."""

from __future__ import annotations

import enum
from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label

_PATH_INPUT_ID = "picker-path"
_PATH_INPUT = f"#{_PATH_INPUT_ID}"


class PickMode(enum.Enum):
    """What the picker returns."""

    FOLDER = "folder"
    OPEN_FILE = "open"
    SAVE_FILE = "save"


def shown_paths(paths: Iterable[Path], folders_only: bool, extensions: Iterable[str]) -> list[Path]:
    """Return the folders in ``paths`` and, unless ``folders_only``, the files with one of ``extensions``.

    An empty ``extensions`` keeps every file.
    """
    wanted = {extension.lstrip(".").casefold() for extension in extensions}
    shown = []
    for path in paths:
        try:
            is_dir = path.is_dir()
        except OSError:
            continue
        if is_dir or (not folders_only and (not wanted or path.suffix.lstrip(".").casefold() in wanted)):
            shown.append(path)
    return shown


class _PathTree(DirectoryTree):
    """Directory tree filtered by :func:`shown_paths`."""

    def __init__(self, path: Path, *, folders_only: bool, extensions: tuple[str, ...], **kwargs) -> None:
        super().__init__(path, **kwargs)
        self._folders_only = folders_only
        self._extensions = extensions

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return shown_paths(paths, self._folders_only, self._extensions)


class PathPicker(ModalScreen[str | None]):
    """Pick a folder, an existing file, or the path of a file to write.

    The path input stays editable, so a destination can be given a new file name.
    Dismisses with the chosen path, or ``None`` when cancelled.
    """

    DEFAULT_CSS = """
    PathPicker {
        align: center middle;
    }

    PathPicker > #dialog {
        width: 90%;
        max-width: 100;
        height: 90%;
        padding: 0 1;
        border: thick $accent;
        background: $surface;
    }

    PathPicker .picker-title {
        width: 100%;
        height: 1;
        color: $accent;
        text-style: bold;
    }

    PathPicker .picker-row {
        width: 100%;
        height: 3;
    }

    PathPicker #picker-dir {
        width: 1fr;
        height: 3;
        padding: 1 0 0 1;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }

    PathPicker #picker-tree {
        height: 1fr;
    }

    PathPicker #picker-path {
        width: 1fr;
    }

    PathPicker Button {
        min-width: 10;
        margin: 0 0 0 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, mode: PickMode, current: str = "", extensions: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._title = title
        self._mode = mode
        self._current = current.strip()
        self._extensions = extensions

    @staticmethod
    def _start_directory(current: str) -> Path:
        path = Path(current).expanduser() if current else Path.cwd()
        for candidate in (path, *path.parents):
            if candidate.is_dir():
                return candidate.resolve()
        return Path.cwd()

    def compose(self) -> ComposeResult:
        """Build the dialog: title, current folder with Up, the tree, and the path row."""
        start = self._start_directory(self._current)
        yield Vertical(
            Label(self._title, classes="picker-title"),
            Horizontal(
                Button("Up", id="picker-up"),
                Label(str(start), id="picker-dir", markup=False),
                classes="picker-row",
            ),
            _PathTree(start, folders_only=self._mode is PickMode.FOLDER, extensions=self._extensions, id="picker-tree"),
            Horizontal(
                Input(self._current, placeholder="path", id=_PATH_INPUT_ID),
                Button("Select", id="picker-select", variant="primary"),
                Button("Cancel", id="picker-cancel"),
                classes="picker-row",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#picker-tree", _PathTree).focus()

    def _set_path(self, path: Path) -> None:
        self.query_one(_PATH_INPUT, Input).value = str(path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Take the folder in folder mode; keep the typed file name in save mode."""
        event.stop()
        if self._mode is PickMode.FOLDER:
            self._set_path(event.path)
        elif self._mode is PickMode.SAVE_FILE:
            name = Path(self.query_one(_PATH_INPUT, Input).value.strip()).name
            self._set_path(event.path / name if name and Path(name).suffix else event.path)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self._set_path(event.path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "picker-up":
            tree = self.query_one("#picker-tree", _PathTree)
            parent = Path(tree.path).parent
            tree.path = parent
            self.query_one("#picker-dir", Label).update(str(parent))
        elif event.button.id == "picker-select":
            self._accept()
        elif event.button.id == "picker-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._accept()

    def _accept(self) -> None:
        value = self.query_one(_PATH_INPUT, Input).value.strip()
        if not value:
            return
        if self._mode is PickMode.SAVE_FILE and self._extensions and not Path(value).suffix:
            value = f"{value}.{self._extensions[0].lstrip('.')}"
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
