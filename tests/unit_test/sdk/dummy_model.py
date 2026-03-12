from typing import Optional, Union

from pydantic import BaseModel


class DummyChild(BaseModel):
    name: str


class DummyDictChild(BaseModel):
    name: str


class DummyUnionChild(BaseModel):
    name: str


class DummyOptionalChild(BaseModel):
    name: str


class DummyNestedChild(BaseModel):
    name: str
    nested_child: DummyChild


class DummyRoot(BaseModel):
    name: str
    child_list: list[DummyChild]
    child_dict: dict[str, DummyDictChild]
    union_child: Union[DummyChild, DummyNestedChild]
    optional_child: Optional[DummyOptionalChild]
    nested_child: DummyNestedChild
    normal_child: DummyChild
