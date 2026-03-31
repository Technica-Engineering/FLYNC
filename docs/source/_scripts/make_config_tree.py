import os
import pathlib

from rich import print
from rich.text import Text
from rich.tree import Tree
from rich.console import Console

EXAMPLE_PATH = r"examples/flync_example"
OUTFILE = r"docs/source/_scripts/generated/flync_tree.rst"


def walk_directory(directory: pathlib.Path, tree: Tree) -> None:
    """Recursively build a Tree with directory contents."""
    # Sort dirs first then by filename
    paths = sorted(
        pathlib.Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )
    for path in paths:
        # Remove hidden files
        if path.name.startswith("."):
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f":open_file_folder: {path.name}",
                style=style,
                guide_style=style,
            )
            walk_directory(path, branch)
        else:
            text_filename = Text(path.name)
            icon = "📄 "
            tree.add(Text(icon) + text_filename)


directory = os.path.abspath(EXAMPLE_PATH)

tree = Tree(
    f"FLYNC Config",
)
walk_directory(pathlib.Path(directory), tree)


with open(OUTFILE, "w") as rst:
    console = Console(file=rst)
    console.print(tree)
