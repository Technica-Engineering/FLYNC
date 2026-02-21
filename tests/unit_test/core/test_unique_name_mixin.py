import pytest
from pydantic import ValidationError

from flync.core.base_models import UniqueName


class TModel(UniqueName):
    pass


class TModel2(UniqueName):
    pass


class TestUniqueNames:

    def test_ecu_port_name_must_be_unique(self):
        with pytest.raises(ValidationError):
            t1 = TModel(name="1")
            t2 = TModel(name="1")

    def test_ecu_port_name_must_allow_different_names(self):
        t1 = TModel(name="1")
        t2 = TModel(name="2")
        assert TModel.NAMES == {"TModel.1", "TModel.2"}

    def test_different_classes_must_allow_same_name(self):
        t1 = TModel(name="1")
        t2 = TModel2(name="1")
        assert TModel.NAMES == {"TModel.1", "TModel2.1"}
