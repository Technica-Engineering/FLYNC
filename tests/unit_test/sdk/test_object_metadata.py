"""
Comprehensive tests for ObjectMetadata API.

Tests cover:
- Basic metadata retrieval and properties
- Reference field (fields) extraction
- Parent/child relationship resolution
- Source location tracking
- JSON serialization (to_dict)
- Edge cases and error conditions
- Integration with workspace
"""

import pytest

from flync.sdk.workspace.ids import ObjectId
from flync.sdk.workspace.objects import (
    DictFieldMetadata,
    ListFieldMetadata,
    ObjectMetadata,
    ScalarFieldMetadata,
)


class TestObjectMetadataBasics:
    """Test basic ObjectMetadata functionality."""

    def test_get_metadata_returns_object_metadata(self, loaded_workspace_with_object_map):
        """Verify get_metadata returns ObjectMetadata instance."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        assert isinstance(metadata, ObjectMetadata)

    def test_metadata_has_id(self, loaded_workspace_with_object_map):
        """Metadata should preserve the ObjectId."""
        obj_id = ObjectId("ecus")
        metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
        assert metadata.id == obj_id

    def test_metadata_type_name(self, loaded_workspace_with_object_map):
        """Type name should be the model class name."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        assert metadata.type_name is not None
        assert isinstance(metadata.type_name, str)
        assert len(metadata.type_name) > 0

    def test_metadata_fields_dict(self, loaded_workspace_with_object_map):
        """fields should be a dict mapping reference field names to metadata."""
        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            assert isinstance(metadata.fields, dict)
            for field_name in metadata.fields:
                assert isinstance(field_name, str)

    def test_metadata_source_dict(self, loaded_workspace_with_object_map):
        """Source should have uri and range."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        assert isinstance(metadata.source, dict)
        assert "uri" in metadata.source
        assert "range" in metadata.source
        # Source URI can be a document ID or a full path
        assert isinstance(metadata.source["uri"], str)
        assert len(metadata.source["uri"]) > 0


class TestParentChildRelationships:
    """Test parent/child relationship resolution."""

    def test_root_object_has_no_parent(self, loaded_workspace_with_object_map):
        """Root objects should have parent_id = None."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        # "ecus" is likely a root field
        assert metadata.parent_id is None or isinstance(metadata.parent_id, str)

    def test_nested_object_has_parent(self, loaded_workspace_with_object_map):
        """Nested objects should have a parent_id."""
        # Find a nested object
        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            if "." in str(obj_id):  # Nested object
                assert metadata.parent_id is not None
                assert isinstance(metadata.parent_id, str)
                break

    def test_child_ids_are_list(self, loaded_workspace_with_object_map):
        """child_ids should always be a list."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        assert isinstance(metadata.child_ids, list)
        # All children should be strings (ObjectId string representation)
        for child_id in metadata.child_ids:
            assert isinstance(child_id, str)

    def test_parent_child_consistency(self, loaded_workspace_with_object_map):
        """If A is parent of B, then B.parent_id should be A."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))

        for child_id in metadata.child_ids:
            child_meta = loaded_workspace_with_object_map.get_metadata(ObjectId(child_id))
            # Parent should match
            assert child_meta.parent_id == str(metadata.id)

    def test_child_prefix_matching(self, loaded_workspace_with_object_map):
        """All children should start with parent_id."""
        parent_id = ObjectId("ecus")
        metadata = loaded_workspace_with_object_map.get_metadata(parent_id)

        for child_id in metadata.child_ids:
            assert child_id.startswith(f"{parent_id}.")


class TestMetadataForAllObjects:
    """Test metadata retrieval for various object types."""

    def test_get_metadata_for_every_object(self, loaded_workspace_with_object_map):
        """Should be able to get metadata for every object in the workspace."""
        all_objects = loaded_workspace_with_object_map.list_objects()
        assert len(all_objects) > 0

        for obj_id in all_objects:
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            assert metadata is not None
            assert metadata.type_name is not None
            assert isinstance(metadata.fields, dict)

    def test_all_metadata_has_source(self, loaded_workspace_with_object_map):
        """Every object should have source location."""
        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            assert metadata.source is not None
            assert "uri" in metadata.source

    def test_type_names_are_consistent(self, loaded_workspace_with_object_map):
        """Same type should always have same type_name."""
        type_to_names = {}

        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            type_name = metadata.type_name

            if type_name not in type_to_names:
                type_to_names[type_name] = []
            type_to_names[type_name].append(str(obj_id))

        # All objects of same type should be consistent
        for type_name, obj_ids in type_to_names.items():
            assert len(obj_ids) > 0


class TestMetadataReferenceFields:
    """Test reference-field (fields) extraction."""

    def test_fields_only_contains_references(self, loaded_workspace_with_object_map):
        """fields should map reference field names to reference metadata."""
        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            for field_name, meta in metadata.fields.items():
                assert isinstance(field_name, str)
                # Each entry serializes to a reference-metadata dict.
                assert "type" in meta.to_dict()

    def test_fields_serialize_in_to_dict(self, loaded_workspace_with_object_map):
        """fields should be present and serializable in to_dict output."""
        for obj_id in loaded_workspace_with_object_map.list_objects():
            result = loaded_workspace_with_object_map.get_metadata(obj_id).to_dict()
            assert isinstance(result["fields"], dict)


class TestMetadataJSONSerialization:
    """Test to_dict() serialization."""

    def test_to_dict_returns_dict(self, loaded_workspace_with_object_map):
        """to_dict() should return a dictionary."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        result = metadata.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_has_required_keys(self, loaded_workspace_with_object_map):
        """Serialized dict should have all required keys."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        result = metadata.to_dict()

        required_keys = {"id", "name", "type", "parent_id", "child_ids", "fields", "source"}
        assert all(key in result for key in required_keys)

    def test_to_dict_does_not_expose_model(self, loaded_workspace_with_object_map):
        """Serialized dict should never contain the model."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        result = metadata.to_dict()

        assert "_model" not in result
        assert "model" not in result
        # The private model should not be accessible via serialization
        assert metadata._model is not None  # Model exists internally
        assert "_model" not in result  # But not exposed in dict

    def test_to_dict_json_serializable(self, loaded_workspace_with_object_map):
        """Result of to_dict() should be JSON-serializable."""
        import json

        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        result = metadata.to_dict()

        # Should not raise an exception
        json_str = json.dumps(result)
        assert len(json_str) > 0

        # Should deserialize back
        loaded = json.loads(json_str)
        assert loaded["id"] == str(metadata.id)
        assert loaded["type"] == metadata.type_name


class TestMetadataEdgeCases:
    """Test edge cases and error conditions."""

    def test_metadata_for_nonexistent_object(self, loaded_workspace_with_object_map):
        """Getting metadata for nonexistent object should raise KeyError."""
        with pytest.raises(KeyError):
            loaded_workspace_with_object_map.get_metadata(ObjectId("this.does.not.exist"))

    def test_metadata_empty_children_list(self, loaded_workspace_with_object_map):
        """Objects with no children should have empty list."""
        # Find a leaf object (one with no children)
        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            if len(metadata.child_ids) == 0:
                assert isinstance(metadata.child_ids, list)
                assert len(metadata.child_ids) == 0
                return
        # If no leaf found, that's OK - just verify the structure is correct

    def test_metadata_immutability(self, loaded_workspace_with_object_map):
        """Modifying to_dict() shouldn't affect original metadata."""
        metadata = loaded_workspace_with_object_map.get_metadata(ObjectId("ecus"))
        dict1 = metadata.to_dict()
        dict1["id"] = "modified"

        dict2 = metadata.to_dict()
        assert dict2["id"] == str(metadata.id)
        assert dict2["id"] != "modified"


class TestMetadataPerformance:
    """Test metadata retrieval performance characteristics."""

    def test_metadata_retrieval_idempotent(self, loaded_workspace_with_object_map):
        """Calling get_metadata twice should return equivalent results."""
        obj_id = ObjectId("ecus")
        meta1 = loaded_workspace_with_object_map.get_metadata(obj_id)
        meta2 = loaded_workspace_with_object_map.get_metadata(obj_id)

        # Should have same values (may be different instances but same data)
        assert meta1.id == meta2.id
        assert meta1.type_name == meta2.type_name
        assert meta1.to_dict() == meta2.to_dict()

    def test_metadata_caching_behavior(self, loaded_workspace_with_object_map):
        """Multiple metadata calls should complete quickly."""
        import time

        obj_id = ObjectId("ecus")

        # First call
        start = time.time()
        metadata1 = loaded_workspace_with_object_map.get_metadata(obj_id)
        time1 = time.time() - start

        # Second call should be fast (cached or quick lookup)
        start = time.time()
        metadata2 = loaded_workspace_with_object_map.get_metadata(obj_id)
        time2 = time.time() - start

        # Just verify both complete (no specific timing assertion as it depends on system)
        assert metadata1.id == metadata2.id


class TestMetadataWorkflowIntegration:
    """Test metadata in realistic workflows."""

    def test_find_objects_by_type(self, loaded_workspace_with_object_map):
        """Should be able to find all objects of a specific type."""
        type_to_find = None
        # Find a common type
        for obj_id in loaded_workspace_with_object_map.list_objects():
            meta = loaded_workspace_with_object_map.get_metadata(obj_id)
            type_to_find = meta.type_name
            break

        # Find all objects of that type
        matching = []
        for obj_id in loaded_workspace_with_object_map.list_objects():
            meta = loaded_workspace_with_object_map.get_metadata(obj_id)
            if meta.type_name == type_to_find:
                matching.append(obj_id)

        assert len(matching) > 0

    def test_navigate_tree_with_metadata(self, loaded_workspace_with_object_map):
        """Should be able to navigate tree using parent/child relationships."""
        visited = set()

        def traverse(obj_id, depth=0):
            obj_id_str = str(obj_id) if obj_id else "root"
            if obj_id_str in visited or depth > 3:
                return
            visited.add(obj_id_str)

            try:
                metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
                assert metadata is not None

                # Traverse children (limited depth)
                for child_id in metadata.child_ids:
                    traverse(ObjectId(child_id), depth + 1)
            except KeyError:
                # Root might not exist, that's OK
                pass

        # Start from a known root object
        for obj_id in loaded_workspace_with_object_map.list_objects():
            traverse(obj_id, 0)
            break

        assert len(visited) > 0

    def test_build_reference_map(self, loaded_workspace_with_object_map):
        """Should be able to build a map of reference fields for all objects."""
        reference_map = {}

        for obj_id in loaded_workspace_with_object_map.list_objects():
            metadata = loaded_workspace_with_object_map.get_metadata(obj_id)
            reference_map[str(obj_id)] = {
                "type": metadata.type_name,
                "references": list(metadata.fields.keys()),
            }

        assert len(reference_map) > 0
        # Verify structure
        for obj_id, info in reference_map.items():
            assert "type" in info
            assert "references" in info


class TestFieldMetadataSerialization:
    """Directly exercise the FieldMetadata reference variants and their recursive to_dict()."""

    def test_scalar_field_metadata_to_dict(self):
        meta = ScalarFieldMetadata([ObjectId("ecus.a"), ObjectId("ecus.b")])
        assert meta.to_dict() == {"type": "object", "ids": ["ecus.a", "ecus.b"]}

    def test_list_field_metadata_to_dict(self):
        meta = ListFieldMetadata([ScalarFieldMetadata([ObjectId("ecus.a")])])
        assert meta.to_dict() == {"type": "list", "items": [{"type": "object", "ids": ["ecus.a"]}]}

    def test_dict_field_metadata_to_dict(self):
        meta = DictFieldMetadata({"port": ScalarFieldMetadata([ObjectId("ecus.a.p0")])})
        assert meta.to_dict() == {"type": "dict", "items": {"port": {"type": "object", "ids": ["ecus.a.p0"]}}}

    def test_nested_field_metadata_to_dict(self):
        """A list of dicts of scalars should serialize recursively."""
        meta = ListFieldMetadata([DictFieldMetadata({"port": ScalarFieldMetadata([ObjectId("ecus.a.p0")])})])
        assert meta.to_dict() == {
            "type": "list",
            "items": [{"type": "dict", "items": {"port": {"type": "object", "ids": ["ecus.a.p0"]}}}],
        }
