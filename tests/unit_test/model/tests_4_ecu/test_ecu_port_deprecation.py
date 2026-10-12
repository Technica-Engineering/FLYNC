import warnings

import pytest

from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort


def _port() -> ECUPort:
    return ECUPort(name="p", mdi_config=BASET1())


def test_internal_component_without_argument_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _port().get_internal_connected_component() is None


def test_internal_component_none_argument_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _port().get_internal_connected_component(None) is None


def test_internal_component_ecus_argument_is_deprecated():
    with pytest.warns(DeprecationWarning, match="ecus"):
        assert _port().get_internal_connected_component([]) is None
