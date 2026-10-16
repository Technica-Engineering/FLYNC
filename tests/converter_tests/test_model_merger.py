"""Tests for flync_converter.model_merger: the merge rules and merges of real models."""

import logging

import pytest

from flync_converter.converters.dbc import DbcConverterConfig
from flync_converter.converters.dbc.converter import DbcConverter
from flync_converter.converters.helpers import pydantic_dump
from flync_converter.model_merger import FLYNCModelMerger, MergeConflict, ModelMergeConflictError, OnConflict, PartialModel

from .API.test_dbc_converter import _BUS_A_DBC, _BUS_B_DBC


def _merge(*mappings, on_conflict=OnConflict.FIRST):
    """Merge mappings named ``s0``, ``s1``, ... and return ``(merged, conflicts)``."""
    return FLYNCModelMerger(on_conflict).merge_mappings([(f"s{index}", mapping) for index, mapping in enumerate(mappings)])


# region merge rules


def test_keys_of_one_source_only_are_taken():
    merged, conflicts = _merge({"a": 1}, {"b": {"c": 2}})

    assert merged == {"a": 1, "b": {"c": 2}}
    assert conflicts == []


def test_named_items_are_merged_by_name_at_every_depth():
    merged, conflicts = _merge(
        {"ecus": [{"name": "A", "controllers": [{"name": "C", "left": 1}]}]},
        {"ecus": [{"name": "B"}, {"name": "A", "controllers": [{"name": "C", "right": 2}]}]},
    )

    assert merged == {"ecus": [{"name": "A", "controllers": [{"name": "C", "left": 1, "right": 2}]}, {"name": "B"}]}
    assert conflicts == []


def test_items_with_duplicate_names_are_merged_by_id():
    """An ambiguous name must not collapse two objects into one."""
    merged, conflicts = _merge(
        {"vlans": [{"name": "v", "id": 1}, {"name": "v", "id": 2}]},
        {"vlans": [{"name": "v", "id": 2, "priority": 3}, {"name": "v", "id": 3}]},
    )

    assert merged == {"vlans": [{"name": "v", "id": 1}, {"name": "v", "id": 2, "priority": 3}, {"name": "v", "id": 3}]}
    assert conflicts == []


def test_name_is_preferred_over_id():
    merged, conflicts = _merge({"items": [{"name": "a", "id": 1}]}, {"items": [{"name": "b", "id": 1}]})

    assert merged == {"items": [{"name": "a", "id": 1}, {"name": "b", "id": 1}]}
    assert conflicts == []


@pytest.mark.parametrize(
    "first, second",
    [
        pytest.param([{"start": 0}, {"start": 8}], [{"start": 0}, {"start": 16}], id="no identity"),
        pytest.param([{"name": "v"}, {"name": "v"}], [{"name": "w"}], id="duplicate names, no id"),
        pytest.param([{"name": "a"}], [{"id": 1}], id="different identities"),
    ],
)
def test_list_whose_items_cannot_be_told_apart_is_kept_whole(first, second):
    """Combining such lists would invent content neither source has."""
    merged, conflicts = _merge({"items": first}, {"items": second})

    assert merged == {"items": first}
    assert [conflict.path for conflict in conflicts] == ["items"]


def test_scalar_list_is_kept_whole():
    """A positional list must not be combined or de-duplicated."""
    merged, conflicts = _merge({"bytes": [0, 0, 1]}, {"bytes": [0, 0, 1, 1]})

    assert merged == {"bytes": [0, 0, 1]}
    assert [conflict.path for conflict in conflicts] == ["bytes"]


def test_empty_list_takes_the_other_side():
    assert _merge({"tags": []}, {"tags": ["x"]})[0] == {"tags": ["x"]}
    assert _merge({"tags": ["x"]}, {"tags": []})[0] == {"tags": ["x"]}


def test_inputs_are_not_modified():
    first, second = {"ecus": [{"name": "A", "x": 1}]}, {"ecus": [{"name": "A", "y": 2}]}

    _merge(first, second)

    assert first == {"ecus": [{"name": "A", "x": 1}]}
    assert second == {"ecus": [{"name": "A", "y": 2}]}


# endregion
# region conflict policy


_FIRST = {"ecus": [{"name": "A", "address": 1}]}
_SECOND = {"ecus": [{"name": "A", "address": 2}]}


def test_first_wins_by_default_and_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="flync_converter.model_merger"):
        merged, conflicts = _merge(_FIRST, _SECOND)

    assert merged == _FIRST
    assert conflicts == [MergeConflict(path="ecus[A].address", kept=1, dropped=2, kept_source="s0", dropped_source="s1")]
    assert "ecus[A].address" in caplog.text


def test_last_wins():
    merged, conflicts = _merge(_FIRST, _SECOND, on_conflict=OnConflict.LAST)

    assert merged == _SECOND
    assert conflicts == [MergeConflict(path="ecus[A].address", kept=2, dropped=1, kept_source="s1", dropped_source="s0")]


def test_error_policy_raises_with_the_path_and_both_sources():
    with pytest.raises(ModelMergeConflictError) as error:
        _merge(_FIRST, _SECOND, on_conflict="error")

    assert error.value.path == "ecus[A].address"
    assert error.value.existing_source == "s0"
    assert error.value.incoming_source == "s1"
    assert "ecus[A].address" in str(error.value)


def test_conflict_names_the_source_that_provided_the_kept_value():
    """With three sources the kept value's source is the one that set it, not the first."""
    _, conflicts = _merge({"ecus": [{"name": "A"}]}, {"ecus": [{"name": "A", "address": 1}]}, {"ecus": [{"name": "A", "address": 2}]})

    assert [(conflict.kept_source, conflict.dropped_source) for conflict in conflicts] == [("s1", "s2")]


def test_conflict_as_mapping_is_plain_data():
    conflict = MergeConflict(path="a", kept=1, dropped=2, kept_source="s0", dropped_source="s1")

    assert conflict.as_mapping() == {"path": "a", "kept": 1, "dropped": 2, "kept_source": "s0", "dropped_source": "s1"}


# endregion
# region real models


def _decode_dbc(folder, name, content):
    folder.mkdir()
    (folder / name).write_text(content, encoding="utf-8")
    return PartialModel(source=str(folder), model=DbcConverter(DbcConverterConfig(config_path=str(folder))).decode())


def _can_interfaces(ecu):
    return [interface.name for controller in ecu.controllers for interface in controller.can_interfaces]


def test_empty_input_is_rejected():
    merger = FLYNCModelMerger()

    with pytest.raises(ValueError):
        merger.merge([])


def test_single_model_is_returned_as_it_is(flync_object):
    result = FLYNCModelMerger().merge([PartialModel(source="a", model=flync_object)])

    assert result.model is flync_object
    assert result.conflicts == ()


def test_two_dbc_sources_unite_the_shared_ecu(tmp_path):
    """NODE3 is on both buses: it must appear once and carry both CAN interfaces."""
    bus_a = _decode_dbc(tmp_path / "a", "bus_a.dbc", _BUS_A_DBC)
    bus_b = _decode_dbc(tmp_path / "b", "bus_b.dbc", _BUS_B_DBC)

    result = FLYNCModelMerger().merge([bus_a, bus_b])

    assert result.conflicts == ()
    ecus = {ecu.name: ecu for ecu in result.model.ecus}
    assert list(ecus) == ["NODE1", "NODE2", "NODE3", "NODE4"]
    assert len(ecus["NODE3"].controllers) == 1
    assert _can_interfaces(ecus["NODE3"]) == ["bus_a", "bus_b"]
    assert [bus.name for bus in result.model.communication.channels.can_buses] == ["bus_a", "bus_b"]


def test_cross_format_merge_keeps_the_first_metadata(tmp_path, flync_object):
    """Every decoder writes its own metadata, so a cross-format merge must not fail on it."""
    workspace = PartialModel(source="workspace", model=flync_object)
    bus_a = _decode_dbc(tmp_path / "a", "bus_a.dbc", _BUS_A_DBC)

    result = FLYNCModelMerger().merge([workspace, bus_a])

    assert result.conflicts
    assert all(conflict.path.startswith("metadata.") for conflict in result.conflicts)
    assert all(conflict.kept_source == "workspace" for conflict in result.conflicts)
    assert result.model.metadata.author == flync_object.metadata.author
    assert len(result.model.ecus) == len(flync_object.ecus) + 3


def test_cross_format_merge_fails_under_the_error_policy(tmp_path, flync_object):
    workspace = PartialModel(source="workspace", model=flync_object)
    bus_a = _decode_dbc(tmp_path / "a", "bus_a.dbc", _BUS_A_DBC)

    merger = FLYNCModelMerger(OnConflict.ERROR)

    with pytest.raises(ModelMergeConflictError, match="metadata"):
        merger.merge([workspace, bus_a])


def test_merging_a_model_with_itself_changes_nothing(flync_object):
    result = FLYNCModelMerger().merge([PartialModel("a", flync_object), PartialModel("b", flync_object)])

    assert result.conflicts == ()
    assert pydantic_dump(result.model) == pydantic_dump(flync_object)


# endregion
