"""Tests for model dependency graph cache invalidation."""

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from flync.sdk.utils.model_dependencies import (
    _hash_model_structure,
    get_model_dependency_graph,
)


# Module-level (pickleable) models for the shelve-cache-key test. They must be
# importable by qualname so ``_is_pickleable_class`` treats them as disk-cacheable
# and the code path actually reaches the (mocked) shelve store. Function-local
# models are non-pickleable and are cached in memory by identity instead, which
# would never populate the shelve mock.
class CacheKeyModelV1(BaseModel):
    field: str


class CacheKeyModelV2(BaseModel):
    field: str
    extra: Optional[int] = None


class TestModelStructureHashing:
    """Test that model structure hashing detects changes in field definitions."""

    def test_hash_changes_when_field_added(self):
        """Hash should change when a new field is added."""

        class ModelV1(BaseModel):
            name: str

        class ModelV2(BaseModel):
            name: str
            age: Optional[int] = None

        hash_v1 = _hash_model_structure(ModelV1)
        hash_v2 = _hash_model_structure(ModelV2)

        assert hash_v1 != hash_v2, "Hash should change when field is added"

    def test_hash_changes_when_field_removed(self):
        """Hash should change when a field is removed."""

        class ModelV1(BaseModel):
            name: str
            age: Optional[int] = None

        class ModelV2(BaseModel):
            name: str

        hash_v1 = _hash_model_structure(ModelV1)
        hash_v2 = _hash_model_structure(ModelV2)

        assert hash_v1 != hash_v2, "Hash should change when field is removed"

    def test_hash_changes_when_field_type_changes(self):
        """Hash should change when a field's type changes."""

        class ModelV1(BaseModel):
            value: int

        class ModelV2(BaseModel):
            value: str

        hash_v1 = _hash_model_structure(ModelV1)
        hash_v2 = _hash_model_structure(ModelV2)

        assert hash_v1 != hash_v2, "Hash should change when field type changes"

    def test_hash_changes_with_field_metadata(self):
        """Hash should change when field metadata (e.g., constraints) changes."""

        class ModelV1(BaseModel):
            count: Optional[int] = Field(default=None, ge=0)

        class ModelV2(BaseModel):
            count: Optional[int] = Field(default=None, ge=1)

        hash_v1 = _hash_model_structure(ModelV1)
        hash_v2 = _hash_model_structure(ModelV2)

        assert hash_v1 != hash_v2, "Hash should change when field metadata changes"

    def test_hash_identical_for_same_model(self):
        """Hash should be identical for the same model structure."""

        class Model(BaseModel):
            name: str
            age: Optional[int] = None

        hash1 = _hash_model_structure(Model)
        hash2 = _hash_model_structure(Model)

        assert hash1 == hash2, "Hash should be consistent for the same model"

    def test_cache_key_includes_hash(self):
        """Verify that cache keys include the model structure hash."""

        ModelV1 = CacheKeyModelV1
        ModelV2 = CacheKeyModelV2

        # Mock shelve so we can observe the disk-cache keys without touching disk.
        # These models are pickleable (module-level), so they take the shelve path.
        mock_cache = {}
        with patch("flync.sdk.utils.model_dependencies.shelve.open") as mock_shelve:
            mock_shelve.return_value.__enter__.return_value = mock_cache

            # Get dependency graphs (which creates cache keys internally)
            graph_v1 = get_model_dependency_graph(ModelV1)
            graph_v2 = get_model_dependency_graph(ModelV2)

            # Both should be valid graphs
            assert graph_v1 is not None
            assert graph_v2 is not None

            # They should be different instances (because the model structure differs)
            assert graph_v1.root != graph_v2.root

            # Verify cache keys differ
            keys = list(mock_cache.keys())
            assert len(keys) == 2, "Should have two different cache entries"
            assert keys[0] != keys[1], "Cache keys should differ for different models"


class TestCacheInvalidationWithExtendedModels:
    """Test that cache invalidation works with extended model hierarchies."""

    def test_extended_pdu_hash_changes_when_extended(self):
        """Hash should differ between standard and extended PDU models."""
        from flync.model.flync_4_signal.pdu import StandardPDU

        # Create an extended version
        class SafetyPDU(StandardPDU):
            safety_level: Optional[str] = Field(default=None)
            diagnostic_capable: bool = Field(default=False)

        hash_standard = _hash_model_structure(StandardPDU)
        hash_extended = _hash_model_structure(SafetyPDU)

        assert hash_standard != hash_extended, "Extended model should have different hash than base"

    def test_cache_distinguishes_extended_models(self):
        """Cache should keep extended model graphs separate from standard."""
        from flync.model.flync_4_signal.pdu import StandardPDU

        class SafetyPDU1(StandardPDU):
            safety_level: Optional[str] = None

        class SafetyPDU2(StandardPDU):
            safety_level: Optional[str] = None
            diagnostic_capable: bool = False

        # Both are extensions but with different fields
        hash1 = _hash_model_structure(SafetyPDU1)
        hash2 = _hash_model_structure(SafetyPDU2)

        assert hash1 != hash2, "Different extensions should have different hashes"

    def test_dynamically_created_model_module_location(self):
        """Test where dynamically created models report their __module__."""
        from flync.model.flync_4_signal.pdu import StandardPDU

        # Manually create a model using type() like create_extended_model does
        DynamicModel = type(
            "DynamicModel",
            (StandardPDU,),
            {"__annotations__": {"test_field": Optional[str]}, "test_field": None},
        )

        # Dynamic model's __module__ comes from where type() was called
        print(f"StandardPDU module: {StandardPDU.__module__}")  # "flync.model.flync_4_signal.pdu"
        print(f"DynamicModel module: {DynamicModel.__module__}")  # "tests.unit_test.sdk.test_model_dependency_cache"

        # Both should hash successfully
        hash_standard = _hash_model_structure(StandardPDU)
        hash_dynamic = _hash_model_structure(DynamicModel)

        assert hash_standard is not None
        assert hash_dynamic is not None
        # They have different structures (DynamicModel has test_field)
        assert hash_standard != hash_dynamic
