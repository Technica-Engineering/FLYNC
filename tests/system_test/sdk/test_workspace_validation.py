"""
Test the validation API of an entire FLYNC workspace
to ensure it reports the errors and state accurately.
"""

import shutil
from pathlib import Path

import pytest

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_workspace

from .helper import absolute_path, update_yaml_content


def test_validate_fully_valid_workspace(tmp_path):
    """
    Validates a correct workspace and check its state.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    result = validate_workspace(absolute_path)
    assert result.model is not None
    assert result.workspace is not None
    assert result.state == WorkspaceState.WARNING
    assert result.errors != {}

    if destination_folder.exists():
        shutil.rmtree(destination_folder)


@pytest.mark.xfail(reason="FLYNC-1293")
def test_validate_empty_workspace(tmp_path):
    """
    Validates an empty workspace and check its state.
    In this test case, 'empty' means an empty folder.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
    """
    empty_workspace = Path(tmp_path) / "empty_workspace"
    empty_workspace.mkdir()

    result = validate_workspace(empty_workspace)

    assert result.model is None
    assert result.workspace is None
    assert result.state == WorkspaceState.EMPTY
    assert result.errors == {}

    if empty_workspace.exists():
        shutil.rmtree(empty_workspace)


def test_validate_workspace_with_blank_files(tmp_path):
    """
    Validates a workspace that contains blank FLYNC files and checks its state.
    In this test case, 'blank' means files exist with correct names but contain no content.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)

    for yml in destination_folder.rglob("*.flync.yaml"):
        yml.write_text("")

    result = validate_workspace(destination_folder)

    assert result.model is None
    assert result.workspace is not None
    assert result.state == WorkspaceState.INVALID
    assert result.errors != {}

    if destination_folder.exists():
        shutil.rmtree(destination_folder)


@pytest.mark.xfail(reason="FLYNC-1294")
def test_validate_workspace_without_flync_files(tmp_path):
    """
    Validates that a workspace containing no .flync.yaml files is considered empty.
    """

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create some unrelated files and folders
    (workspace / "README.md").write_text("# Test workspace")
    (workspace / "notes.txt").write_text("Nothing to load.")

    (workspace / "docs").mkdir()
    (workspace / "cache").mkdir()
    (workspace / "logs").mkdir()

    result = validate_workspace(workspace)

    assert result.model is None
    assert result.workspace is None
    assert result.state == WorkspaceState.EMPTY

    if workspace.exists():
        shutil.rmtree(workspace)


TYPE_AND_SEMANTIC_ERROR_SCENARIOS = [
    {
        "sceanrio_name": "int_value_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: 123",
    },
    {
        "sceanrio_name": "empty_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: ",
    },
    {
        "sceanrio_name": "null_value_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: null",
    },
    {
        "sceanrio_name": "boolean_value_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: true",
    },
    {
        "sceanrio_name": "incorrect_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: z1_s1_p2",
    },
    {
        "sceanrio_name": "extra_field_under_name",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "- name: z1_s1_p0\n  config:",
    },
]


@pytest.mark.parametrize(
    "sceanrio",
    TYPE_AND_SEMANTIC_ERROR_SCENARIOS,
    ids=[s["sceanrio_name"] for s in TYPE_AND_SEMANTIC_ERROR_SCENARIOS],
)
@pytest.mark.xfail(reason="FLYNC-1295")
def test_validate_workspace_with_a_content_error(tmp_path, sceanrio: dict):
    """
    Validates that a workspace with a specific content error is reported with diagnostics.

    The test creates a copy of flync_example workspace, injects a single syntax/semantic mistake as described by the scenario,
    runs the SDK validator and checks that the resulting DiagnosticsResult has the state 'WARNING' with at least one error.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
        sceanrio: Dictionary describing the modification to apply.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)

    update_yaml_content(
        destination_folder / sceanrio["file_path"],
        sceanrio["old_text"],
        sceanrio["new_text"],
    )
    result = validate_workspace(destination_folder)

    assert result.workspace is not None
    assert result.state == WorkspaceState.INVALID
    assert result.model is not None
    assert result.errors != {}

    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_validate_workspace_with_duplicate_yaml_key(tmp_path):
    """
    Validates that a workspace with a duplicate YAML key is marked as BROKEN.

    A duplicate YAML key prevents the YAML parser from constructing the node,
    so the workspace cannot be loaded successfully.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)

    file_path = destination_folder / "ecus/zonal_platform1/switches/z1_switch1.flync.yaml"

    update_yaml_content(
        file_path,
        "- name: z1_s1_p0",
        "- name: z1_s1_p0\n  name: z1_s1_p0",
    )

    result = validate_workspace(destination_folder)

    assert result.state == WorkspaceState.BROKEN
    assert result.workspace is None
    assert result.model is None
    assert result.errors == {}


STRUCTURAL_SCENARIOS = [
    {
        "sceanrio_name": "broken_indentation",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": " - name: z1_s1_p0",
    },
    {
        "sceanrio_name": "missing_list_marker",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": " name: z1_s1_p0",
    },
    {
        "sceanrio_name": "missing_space_after_list_marker",
        "file_path": "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "old_text": "- name: z1_s1_p0",
        "new_text": "-name: z1_s1_p0",
    },
]


@pytest.mark.parametrize(
    "sceanrio2",
    STRUCTURAL_SCENARIOS,
    ids=[s["sceanrio_name"] for s in STRUCTURAL_SCENARIOS],
)
@pytest.mark.xfail(reason="FLYNC-1296")
def test_validate_workspace_with_incorrect_structure(tmp_path, sceanrio2: dict):
    """
    Validates that a workspace with a structural YAML issue is marked as BROKEN.

    The test creates a copy of flync_example workspace, injects a single structural mistake as described by the scenario,
    runs the SDK validator and checks that the resulting DiagnosticsResult has the state 'BROKEN' with no workspace loaded.

    Args:
        tmp_path: A pytest fixture that provides an empty temporary directory.
        sceanrio: Dictionary describing the modification to apply.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)

    update_yaml_content(
        destination_folder / sceanrio2["file_path"],
        sceanrio2["old_text"],
        sceanrio2["new_text"],
    )
    result = validate_workspace(destination_folder)

    assert result.workspace is None
    assert result.state == WorkspaceState.BROKEN
    assert result.model is None
    assert result.errors != {}

    if destination_folder.exists():
        shutil.rmtree(destination_folder)
