import io

import pytest

from flync.core.utils import yaml_io


def test_yaml_12_scalars_stay_strings_or_plain_ints():
    data = yaml_io.safe_load("a: yes\nb: off\nc: 0875\nd: 00:11:22:33:44:55\ne: 0x1F\nf: 0o17\ng: true\n")
    assert data == {"a": "yes", "b": "off", "c": 875, "d": "00:11:22:33:44:55", "e": 31, "f": 15, "g": True}


def test_empty_document_is_none():
    assert yaml_io.safe_load("") is None


def test_duplicate_keys_raise():
    with pytest.raises(yaml_io.YAMLError, match="duplicate key 'a'"):
        yaml_io.safe_load("a: 1\na: 2\n")


def test_merge_key_override_is_not_a_duplicate():
    assert yaml_io.safe_load("x: &a {k: 1}\ny:\n  <<: *a\n  k: 2\n")["y"] == {"k": 2}


def test_dump_keeps_order_unicode_and_quotes_ambiguous_strings():
    text = yaml_io.safe_dump({"z": "0875", "a": "äö", "t": "true", "l": [1, 2]})
    assert text == "z: '0875'\na: äö\nt: 'true'\nl:\n- 1\n- 2\n"
    assert yaml_io.safe_load(text) == {"z": "0875", "a": "äö", "t": "true", "l": [1, 2]}


def test_dump_to_stream_returns_none():
    stream = io.StringIO()
    assert yaml_io.safe_dump({"a": 1}, stream) is None
    assert stream.getvalue() == "a: 1\n"


def test_compose_carries_positions():
    node = yaml_io.compose("a:\n  b: 1\n")
    inner = node.value[0][1]
    assert (inner.start_mark.line, inner.start_mark.column) == (1, 2)
