import pytest


@pytest.fixture(scope="session")
def flync_model(example_workspace_path):
    """An already-loaded, already-validated FLYNCModel from the reference topology.

    The instrumentation overlay's measurement points name real buses, segments and ECU ports, so
    resolving them needs the finished object graph rather than a hand-built stub. Scoped to this
    directory because only the instrumentation bind tests need it; ``example_workspace_path`` comes
    from the root conftest.
    """
    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

    workspace = FLYNCWorkspace.load_workspace(
        workspace_name="flync_example",
        workspace_path=str(example_workspace_path),
    )
    return workspace.flync_model
