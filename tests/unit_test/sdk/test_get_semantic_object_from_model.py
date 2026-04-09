import pytest

from flync.sdk.workspace.objects import SemanticObject

STORED_MODELS = [
    pytest.param(
        lambda ws: ws.flync_model.general,
        "general",
        id="FLYNCGeneralConfig",
    ),
    pytest.param(
        lambda ws: ws.flync_model.general.someip_config,
        "general.someip_config",
        id="SOMEIPConfig",
    ),
]


@pytest.mark.parametrize("get_model,expected_id", STORED_MODELS)
def test_get_semantic_object_from_model_found(
    loaded_workspace, get_model, expected_id
):
    model = get_model(loaded_workspace)
    result = loaded_workspace.get_semantic_object_from_model(model)
    assert result is not None
    assert isinstance(result, SemanticObject)
    assert result.model == model
    assert result.id == expected_id
    assert result.id in loaded_workspace.list_objects()
    assert loaded_workspace.get_object(result.id) is result


def test_get_semantic_object_from_model_returns_none_for_unregistered(
    loaded_workspace,
):
    # The root FLYNCModel is assembled from file-level objects but is never
    # stored in the objects dict itself.
    result = loaded_workspace.get_semantic_object_from_model(
        loaded_workspace.flync_model
    )
    assert result is None
