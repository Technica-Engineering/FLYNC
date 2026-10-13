"""
Verify that hidden files and folders in a workspace are ignored by the loader.

Tooling drops dot-prefixed artifacts (``.git``, ``.approval_tests_temp``, editor
state) anywhere in the tree. The loader used to treat a hidden folder next to the
ECU folders as an ECU and crashed while descending into it.
"""

import shutil
from pathlib import Path

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

from .helper import absolute_path


def test_load_workspace_ignores_hidden_entries(tmp_path):
    """A hidden folder and file beside the ECU folders do not break the load."""
    destination_folder = Path(tmp_path) / "flync_example"
    shutil.copytree(absolute_path, destination_folder)

    hidden_folder = destination_folder / "ecus" / ".approval_tests_temp"
    hidden_folder.mkdir(exist_ok=True)
    (hidden_folder / "approve_all.py").write_text("# tool artifact\n", encoding="utf-8")
    (destination_folder / "ecus" / ".DS_Store").write_text("", encoding="utf-8")

    workspace = FLYNCWorkspace.load_workspace("flync_example", destination_folder)

    assert workspace is not None
    assert workspace.flync_model is not None
    assert workspace.flync_model.ecus
    assert all(ecu.name != ".approval_tests_temp" for ecu in workspace.flync_model.ecus)
