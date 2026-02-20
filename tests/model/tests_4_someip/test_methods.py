import pytest
import pydantic_yaml
from pydantic import ValidationError

from flync.model.flync_4_someip import (
    ArrayType,
    SInt16,
    SInt32,
    SInt8,
    SOMEIPFireAndForgetMethod,
    SOMEIPMethod,
    SOMEIPRequestResponseMethod,
    SOMEIPParameter,
    Struct,
    UInt16,
    UInt32,
    UInt8,
)


def test_simple_method():
    # Method is an abstractclass, so we should not be able to instantiate it
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class SOMEIPMethod.*"
    ):
        m = SOMEIPMethod(
            type="request_response", id=0x123, name="this shall not work"
        )


@pytest.mark.parametrize(
    "input_params",
    [
        pytest.param([], id="None"),  # No input type
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt8())], id="UInt8"
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt16())], id="UInt16"
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt32())], id="UInt32"
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt8())], id="SInt8"
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt16())], id="SInt16"
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt32())], id="SInt32"
        ),
        pytest.param(
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=Struct(name="STRUCT", members=[UInt8()]),
                )
            ],
            id="Struct",
        ),
        pytest.param(
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=ArrayType(
                        name="ARRAY",
                        type="array",
                        dimensions=[
                            {"kind": "dynamic", "length_of_length_field": 32}
                        ],
                        element_type=UInt32(name="UINT32"),
                    ),
                ),
                SOMEIPParameter(
                    name="p2",
                    datatype=ArrayType(
                        name="ARRAY",
                        type="array",
                        dimensions=[{"kind": "fixed", "length": 8}],
                        element_type=UInt8(name="UINT8"),
                    ),
                ),
            ],
            id="Array",
        ),
        pytest.param(
            [None], id="Invalid dict containing None", marks=pytest.mark.xfail
        ),
        pytest.param(10, id="Invalid input int", marks=pytest.mark.xfail),
    ],
)
class TestFireForgetMethod:
    def test_fire_forget_method_input_params(self, input_params):
        """we just try to parse the Method to see how it handles our input"""
        SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            input_parameters=input_params,
        )

    def test_fire_forget_method_from_yaml_matches_constructed(
        self, input_params
    ):
        f = SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            input_parameters=input_params,
        )
        yaml_representation = pydantic_yaml.to_yaml_str(f)
        print(yaml_representation)
        from_yaml = pydantic_yaml.parse_yaml_raw_as(
            SOMEIPFireAndForgetMethod, yaml_representation
        )
        assert from_yaml.model_dump() == f.model_dump()

    def test_fire_forget_missing_type_raises(self, input_params):
        """We expect a ValidationError when type is missing."""
        with pytest.raises(ValidationError):
            SOMEIPFireAndForgetMethod(
                name="f&f",
                id=0x123,
                type=None,
                input_parameters=input_params,
            )


@pytest.mark.parametrize(
    "input_params,output_params",
    [
        pytest.param(
            [], [], id="None", marks=pytest.mark.xfail
        ),  # No return value, forbidden
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt8())],
            [SOMEIPParameter(name="p1", datatype=UInt8())],
            id="UInt8",
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt16(endianness="BE"))],
            [SOMEIPParameter(name="p1", datatype=UInt16(endianness="LE"))],
            id="UInt16",
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=UInt32())],
            [SOMEIPParameter(name="p1", datatype=UInt32())],
            id="UInt32",
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt8())],
            [SOMEIPParameter(name="p1", datatype=SInt8())],
            id="SInt8",
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt16())],
            [SOMEIPParameter(name="p1", datatype=SInt16())],
            id="SInt16",
        ),
        pytest.param(
            [SOMEIPParameter(name="p1", datatype=SInt32())],
            [SOMEIPParameter(name="p1", datatype=SInt32())],
            id="SInt32",
        ),
        pytest.param(
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=Struct(
                        name="STRUCT", members=[UInt8(name="UINT8")]
                    ),
                )
            ],
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=Struct(
                        name="STRUCT", members=[UInt8(name="UINT8")]
                    ),
                )
            ],
            id="Struct",
        ),
        pytest.param(
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=ArrayType(
                        name="ARRAY",
                        # type="array",
                        dimensions=[
                            {"kind": "dynamic", "length_of_length_field": 32}
                        ],
                        element_type=UInt8(name="UINT8"),
                    ),
                )
            ],
            [
                SOMEIPParameter(
                    name="p1",
                    datatype=ArrayType(
                        name="ARRAY",
                        type="array",
                        dimensions=[{"kind": "fixed", "length": 32}],
                        element_type=UInt8(name="UINT8"),
                    ),
                )
            ],
            id="Array",
        ),
        pytest.param(
            [None],
            None,
            id="Invalid dict containing None",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            10, None, id="Invalid input int", marks=pytest.mark.xfail
        ),
    ],
)
class TestRequestAndResponseMethod:
    def test_request_response_method_input_params(
        self, input_params, output_params
    ):
        """we just try to parse the Method to see how it handles our input"""
        SOMEIPRequestResponseMethod(
            name="r&r",
            id=0x123,
            type="request_response",
            input_parameters=input_params,
            output_parameters=output_params,
        )

    def test_request_response_method_from_yaml_matches_constructed(
        self, input_params, output_params
    ):
        f = SOMEIPRequestResponseMethod(
            name="r&r",
            id=0x123,
            type="request_response",
            input_parameters=input_params,
            output_parameters=output_params,
        )
        yaml_representation = pydantic_yaml.to_yaml_str(f)

        from_yaml = pydantic_yaml.parse_yaml_raw_as(
            SOMEIPRequestResponseMethod, yaml_representation
        )
        assert from_yaml.model_dump() == f.model_dump()

    def test_request_response_method_no_output_params_raises(
        self, input_params, output_params
    ):
        """Extra test to ensure ValidationError is raised when output_parameters is empty."""
        if not output_params:
            with pytest.raises(ValidationError):
                SOMEIPRequestResponseMethod(
                    name="r&r",
                    id=0x123,
                    type="request_response",
                    input_parameters=input_params,
                    output_parameters=output_params,
                )

    def test_request_response_missing_type_raises(
        self, input_params, output_params
    ):
        """We expect a ValidationError when type is missing."""
        with pytest.raises(ValidationError):
            SOMEIPRequestResponseMethod(
                name="r&r",
                id=0x123,
                type=None,
                input_parameters=input_params,
                output_parameters=output_params,
            )
