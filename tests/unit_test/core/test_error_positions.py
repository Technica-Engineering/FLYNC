from ruamel.yaml import YAML

from flync.core.utils.exceptions_handling import locate_errors, safe_yaml_position

SOURCE = """\
aging_time: not_a_number
ports:
- name: p0
  sync_config:
    type: time_transmitter
    two_step: maybe
"""


def _compose(text: str = SOURCE):
    return YAML(typ="rt").compose(text)


def _error(loc, **ctx):
    return {"type": "major", "msg": "bad", "loc": loc, "input": None, "ctx": ctx}


class TestSafeYamlPositionOnComposedNodes:
    def test_top_level_value(self):
        assert safe_yaml_position(_compose(), ("aging_time",)) == (1, 13)

    def test_nested_value_through_list_index(self):
        assert safe_yaml_position(_compose(), ("ports", 0, "sync_config", "two_step")) == (6, 15)

    def test_union_tag_segment_is_skipped(self):
        loc = ("ports", 0, "sync_config", "time_transmitter", "two_step")
        assert safe_yaml_position(_compose(), loc) == (6, 15)

    def test_missing_key_falls_back_to_parent(self):
        assert safe_yaml_position(_compose(), ("ports", 0, "absent")) == (3, 3)

    def test_out_of_range_index_falls_back_to_parent(self):
        assert safe_yaml_position(_compose(), ("ports", 5)) == (3, 1)


class TestLocateErrors:
    def test_stamps_position_on_error_without_one(self):
        errors = [_error(("aging_time",))]
        locate_errors(errors, None, _compose())
        assert (errors[0]["ctx"]["line"], errors[0]["ctx"]["col"]) == (1, 13)

    def test_refines_with_first_sub_error(self):
        errors = [_error(("ports", 0, "sync_config"), sub_errors="time_transmitter.two_step: Input should be a valid boolean")]
        locate_errors(errors, None, _compose())
        assert (errors[0]["ctx"]["line"], errors[0]["ctx"]["col"]) == (6, 15)

    def test_creates_ctx_when_error_has_none(self):
        error = _error(("aging_time",))
        del error["ctx"]
        locate_errors([error], None, _compose())
        assert error["ctx"]["line"] == 1

    def test_keeps_existing_position(self):
        errors = [_error(("aging_time",), line=4, col=2)]
        locate_errors(errors, None, _compose())
        assert (errors[0]["ctx"]["line"], errors[0]["ctx"]["col"]) == (4, 2)

    def test_error_without_location_is_left_alone(self):
        errors = [_error(())]
        locate_errors(errors, None, _compose())
        assert "line" not in errors[0]["ctx"]

    def test_no_source_tree_is_a_no_op(self):
        errors = [_error(("aging_time",))]
        locate_errors(errors, None, None)
        assert "line" not in errors[0]["ctx"]
