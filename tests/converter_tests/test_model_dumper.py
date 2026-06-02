"""Tests for flync.sdk.utils.model_dumper — dump_model_with_discriminators."""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field

from flync.sdk.utils.model_dumper import dump_model_with_discriminators


class SimpleModel(BaseModel):
    """Simple test model with discriminator field."""

    name: str
    kind: str = Field(default="default_kind")


class TestDumpModelWithDiscriminators:
    def test_normal_dump_without_graph(self):
        """Test basic dump when graph is unavailable."""
        model = SimpleModel(name="test")
        result = dump_model_with_discriminators(model)
        assert result["name"] == "test"
        assert result["kind"] == "default_kind"

    def test_preserves_model_dump_kwargs(self):
        """Test that kwargs are passed through to model_dump."""
        model = SimpleModel(name="test", kind="custom")
        result = dump_model_with_discriminators(model, exclude={"kind"})
        assert "name" in result
        assert "kind" not in result

    def test_handles_import_error_on_flync_model(self):
        """Test graceful fallback when FLYNCModel import fails."""
        model = SimpleModel(name="test")
        with patch("flync.model.FLYNCModel", side_effect=ImportError("No module")):
            result = dump_model_with_discriminators(model)
            assert result["name"] == "test"

    def test_handles_graph_unavailable(self):
        """Test fallback when get_model_dependency_graph raises exception."""
        model = SimpleModel(name="test")

        with patch("flync.sdk.utils.model_dependencies.get_model_dependency_graph") as mock_graph:
            mock_graph.side_effect = Exception("Graph cache not available")
            result = dump_model_with_discriminators(model)
            assert result["name"] == "test"

    def test_handles_attribute_error_on_graph_fields(self):
        """Test when graph doesn't have fields_info attribute."""
        model = SimpleModel(name="test")

        with patch("flync.sdk.utils.model_dependencies.get_model_dependency_graph") as mock_graph:
            mock_graph.return_value = MagicMock(spec=[])  # No fields_info attribute
            result = dump_model_with_discriminators(model)
            assert result["name"] == "test"

    def test_model_not_in_graph(self):
        """Test when model class is not in the dependency graph."""
        model = SimpleModel(name="test")

        with patch("flync.sdk.utils.model_dependencies.get_model_dependency_graph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph_instance.fields_info = {}  # Model not in graph
            mock_graph.return_value = mock_graph_instance

            result = dump_model_with_discriminators(model)
            assert result["name"] == "test"

    def test_node_info_without_discriminators(self):
        """Test when node_info exists but has no discriminator fields."""
        model = SimpleModel(name="test")

        with patch("flync.sdk.utils.model_dependencies.get_model_dependency_graph") as mock_graph:
            mock_node_info = MagicMock()
            mock_node_info.discriminator_fields = set()

            mock_graph_instance = MagicMock()
            mock_graph_instance.fields_info = {"SimpleModel": mock_node_info}
            mock_graph.return_value = mock_graph_instance

            result = dump_model_with_discriminators(model)
            assert result["name"] == "test"

    def test_updates_model_fields_set_when_discriminators_found(self):
        """Test that discriminator fields are added to model_fields_set."""
        model = SimpleModel(name="test")

        with patch("flync.sdk.utils.model_dependencies.get_model_dependency_graph") as mock_graph:
            mock_node_info = MagicMock()
            mock_node_info.discriminator_fields = {"kind"}

            mock_graph_instance = MagicMock()
            mock_graph_instance.fields_info = {"SimpleModel": mock_node_info}
            mock_graph.return_value = mock_graph_instance

            result = dump_model_with_discriminators(model)

            assert result["name"] == "test"
            assert result["kind"] == "default_kind"

    def test_mode_json_parameter(self):
        """Test that mode='json' is passed through to model_dump."""
        model = SimpleModel(name="test")
        result = dump_model_with_discriminators(model, mode="json")
        assert isinstance(result, dict)
        assert result["name"] == "test"

    def test_exclude_unset_parameter(self):
        """Test that exclude_unset parameter works correctly."""
        model = SimpleModel(name="test")
        result = dump_model_with_discriminators(model, exclude_unset=True)
        assert "name" in result
        assert result["name"] == "test"
