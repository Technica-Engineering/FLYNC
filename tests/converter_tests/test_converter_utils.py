"""Tests for flync_converter.utils — cast_value, get_config_model, _unwrap_optional."""

from typing import Optional, Union
from unittest.mock import MagicMock, patch

import pytest

from flync_converter.base import ConverterConfig
from flync_converter.utils import _is_concrete_config, _unwrap_optional, cast_value, get_config_model


class TestUnwrapOptional:
    def test_plain_type_unchanged(self):
        assert _unwrap_optional(int) is int

    def test_optional_unwraps_to_inner(self):
        hint = Optional[str]
        result = _unwrap_optional(hint)
        assert result is str

    def test_union_with_none_unwraps(self):
        hint = Union[int, None]
        result = _unwrap_optional(hint)
        assert result is int

    def test_union_without_none_returns_first(self):
        hint = Union[int, str]
        result = _unwrap_optional(hint)
        assert result is int


class TestIsConcreteConfig:
    def test_base_config_is_not_concrete(self):
        assert _is_concrete_config(ConverterConfig) is False

    def test_subclass_is_concrete(self):
        class MyConfig(ConverterConfig):
            pass

        assert _is_concrete_config(MyConfig) is True

    def test_non_type_returns_false(self):
        assert _is_concrete_config("not a type") is False

    def test_unrelated_type_returns_false(self):
        assert _is_concrete_config(str) is False


class TestGetConfigModel:
    def test_falls_back_to_base_for_plain_converter(self):
        fake_conv = MagicMock(spec=[])
        with patch("flync_converter.utils.registry", {"plain": fake_conv}):
            result = get_config_model("plain")
        assert result is ConverterConfig

    def test_finds_config_via_init_annotation(self):
        class MyConfig(ConverterConfig):
            pass

        class MyConverter:
            def __init__(self, config: Optional[MyConfig] = None):
                self.config = config

        fake_conv = MyConverter()
        with patch("flync_converter.utils.registry", {"myconv": fake_conv}):
            result = get_config_model("myconv")
        assert result is MyConfig

    def test_finds_config_via_class_attribute(self):
        class MyConfig(ConverterConfig):
            pass

        class MyConverter:
            Config = MyConfig

        fake_conv = MyConverter()
        with patch("flync_converter.utils.registry", {"attr": fake_conv}):
            result = get_config_model("attr")
        assert result is MyConfig or result is ConverterConfig

    def test_unknown_key_returns_base(self):
        with patch("flync_converter.utils.registry", {}):
            result = get_config_model("nonexistent")
        assert result is ConverterConfig

    def test_finds_config_via_class_mro_annotation(self):
        class MyConfig(ConverterConfig):
            pass

        class MyConverter:
            config: Optional[MyConfig] = None

            def __init__(self):
                pass

        fake_conv = MyConverter()
        with patch("flync_converter.utils.registry", {"annotated": fake_conv}):
            result = get_config_model("annotated")
        assert result is MyConfig


class TestCastValue:
    def test_none_returns_none(self):
        assert cast_value(None, int) is None

    def test_int_cast(self):
        assert cast_value("42", int) == 42

    def test_float_cast(self):
        assert cast_value("3.14", float) == pytest.approx(3.14)

    def test_bool_true_variants(self):
        for v in ("1", "true", "yes", "y", "True", "YES"):
            assert cast_value(v, bool) is True

    def test_bool_false_variants(self):
        for v in ("0", "false", "no", "n", "False", "NO"):
            assert cast_value(v, bool) is False

    def test_bool_other_truthy_string(self):
        result = cast_value("maybe", bool)
        assert result is True

    def test_int_cast_failure_returns_string(self):
        result = cast_value("not_a_number", int)
        assert result == "not_a_number"

    def test_float_cast_failure_returns_string(self):
        result = cast_value("not_a_float", float)
        assert result == "not_a_float"

    def test_unknown_type_returns_string(self):
        assert cast_value("hello", str) == "hello"

    def test_unknown_type_object_returns_string(self):
        assert cast_value("hello", object) == "hello"
