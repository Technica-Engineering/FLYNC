"""defines the base class each datatype shares"""

from typing import (
    Annotated,
    ClassVar,
    List,
    Literal,
    Optional,
    Union,
)

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from flync.core.base_models import FLYNCBaseModel
from flync.core.datatypes import Datatype
from flync.core.utils.exceptions import err_minor


class PrimitiveDatatype(Datatype):
    """
    Base class for primitive datatypes such as integers, floating-point
    values, or booleans.

    Parameters
    ----------
    name : str
        Unique name of the datatype.

    description : str, optional
        Human-readable description of the datatype.

    type : str
        Discriminator identifying the concrete primitive datatype kind.

    endianness : Literal["BE", "LE"], optional
        Byte order used for encoding multi-byte values. Defaults to
        big-endian ("BE").
    """


class ComplexDatatype(Datatype):
    """
    Base class for complex datatypes such as structures, arrays, or unions.

    Parameters
    ----------
    name : str
        Unique name of the datatype.

    description : str, optional
        Human-readable description of the datatype.

    type : str
        Discriminator identifying the concrete complex datatype kind.

    endianness : Literal["BE", "LE"], optional
        Byte order used for encoding multi-byte values. Defaults to
        big-endian ("BE").
    """


class Boolean(PrimitiveDatatype):
    """
    Boolean primitive datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"BOOLEAN"``.

    type : Literal["boolean"]
        Discriminator identifying the primitive boolean datatype.
    """

    name: str = Field(default="BOOLEAN")
    type: Literal["boolean"] = Field("boolean")


class BaseInt(PrimitiveDatatype):
    """
    Base class for all integer primitive datatypes.

    This class provides shared semantics for signed and unsigned integer
    representations and defines common descriptive metadata.

    """

    MAX_APPLICATIVE_VALUE_DESC: ClassVar[str] = (
        "the maximum value to define by application"
    )


class BaseFloat(PrimitiveDatatype):
    """
    Base class for all floating-point primitive datatypes.

    This class provides shared semantics for floating-point representations
    and defines common descriptive metadata.

    """

    MAX_APPLICATIVE_VALUE_DESC: ClassVar[str] = (
        "the maximum value to define by application"
    )


class UInt8(BaseInt):
    """
    Unsigned 8-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"UINT_8"``.

    type : Literal["uint8"]
        Discriminator identifying this datatype.

    signed : Literal[False]
        Indicates that the integer is unsigned.

    bit_size : int
        Storage size in bits. Defaults to 8.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="UINT_8")
    type: Literal["uint8"] = Field("uint8")  # type: ignore
    signed: Literal[False] = Field(False)
    bit_size: Annotated[int, Field(gt=0, le=8, default=8)]
    max_applicative_value: Annotated[int, Field(ge=0, le=255)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=255
    )  # type: ignore


class UInt16(BaseInt):
    """
    Unsigned 16-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"UINT_16"``.

    type : Literal["uint16"]
        Discriminator identifying this datatype.

    signed : Literal[False]
        Indicates that the integer is unsigned.

    bit_size : int
        Storage size in bits. Defaults to 16.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="UINT_16")

    type: Literal["uint16"] = Field("uint16")  # type: ignore
    signed: Literal[False] = Field(False)
    bit_size: Annotated[int, Field(gt=8, le=16, default=16)]
    max_applicative_value: Annotated[int, Field(ge=0, le=65535)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=65535
    )


class UInt32(BaseInt):
    """
    Unsigned 32-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"UINT_32"``.

    type : Literal["uint32"]
        Discriminator identifying this datatype.

    signed : Literal[False]
        Indicates that the integer is unsigned.

    bit_size : int
        Storage size in bits. Defaults to 32.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="UINT_32")
    type: Literal["uint32"] = Field("uint32")  # type: ignore
    signed: Literal[False] = Field(False)
    bit_size: Annotated[int, Field(gt=16, le=32, default=32)]
    max_applicative_value: Annotated[int, Field(ge=0, le=4294967295)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=4294967295
    )


class UInt64(BaseInt):
    """
    Unsigned 64-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"UINT_64"``.

    type : Literal["uint64"]
        Discriminator identifying this datatype.

    signed : Literal[False]
        Indicates that the integer is unsigned.

    bit_size : int
        Storage size in bits. Defaults to 64.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="UINT_64")
    type: Literal["uint64"] = Field("uint64")  # type: ignore
    signed: Literal[False] = Field(False)
    bit_size: Annotated[int, Field(gt=32, le=64, default=64)]
    max_applicative_value: Annotated[int, Field(ge=0, le=2**64)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=2**64
    )


class SInt8(BaseInt):
    """
    Signed 8-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"SINT_8"``.

    type : Literal["sint8"]
        Discriminator identifying this datatype.

    signed : Literal[True]
        Indicates that the integer is signed.

    bit_size : int
        Storage size in bits. Defaults to 8.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="SINT_8")
    type: Literal["sint8"] = Field("sint8")  # type: ignore
    signed: Literal[True] = Field(True)
    bit_size: Annotated[int, Field(gt=0, le=8, default=8)]
    max_applicative_value: Annotated[int, Field(ge=-128, le=127)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=127
    )


class SInt16(BaseInt):
    """
    Signed 16-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"SINT_16"``.

    type : Literal["sint16"]
        Discriminator identifying this datatype.

    signed : Literal[True]
        Indicates that the integer is signed.

    bit_size : int
        Storage size in bits. Defaults to 16.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="SINT_16")
    type: Literal["sint16"] = Field("sint16")  # type: ignore
    signed: Literal[True] = Field(True)
    bit_size: Annotated[int, Field(gt=8, le=16, default=16)]
    max_applicative_value: Annotated[int, Field(ge=-32768, le=32767)] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=32767
    )


class SInt32(BaseInt):
    """
    Signed 32-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"SINT_32"``.

    type : Literal["sint32"]
        Discriminator identifying this datatype.

    signed : Literal[True]
        Indicates that the integer is signed.

    bit_size : int
        Storage size in bits. Defaults to 32.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="SINT_32")
    type: Literal["sint32"] = Field("sint32")  # type: ignore
    signed: Literal[True] = Field(True)
    bit_size: Annotated[int, Field(gt=16, le=32, default=32)]
    max_applicative_value: Annotated[
        int, Field(ge=-2147483648, le=2147483647)
    ] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC, default=2147483647
    )


class SInt64(BaseInt):
    """
    Signed 64-bit integer datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"SINT_64"``.

    type : Literal["sint64"]
        Discriminator identifying this datatype.

    signed : Literal[True]
        Indicates that the integer is signed.

    bit_size : int
        Storage size in bits. Defaults to 64.

    max_applicative_value : int
        Maximum application-level value allowed for this datatype.
    """

    name: str = Field(default="SINT_64")
    type: Literal["sint64"] = Field("sint64")  # type: ignore
    signed: Literal[True] = Field(True)
    bit_size: Annotated[int, Field(gt=32, le=64, default=64)]
    max_applicative_value: Annotated[
        int, Field(ge=-9223372036854775808, le=9223372036854775807)
    ] = Field(
        description=BaseInt.MAX_APPLICATIVE_VALUE_DESC,
        default=9223372036854775807,
    )


class Float32(PrimitiveDatatype):
    """
    32-bit floating-point datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"FLOAT_32"``.

    type : Literal["float32"]
        Discriminator identifying this datatype.

    max_applicative_value : float
        Maximum application-level absolute value allowed.
    """

    name: str = Field(default="FLOAT_32")
    type: Literal["float32"] = Field("float32")  # type: ignore
    max_applicative_value: Annotated[
        float, Field(ge=-3.4028235e38, le=3.4028235e38)
    ] = Field(description=BaseFloat.MAX_APPLICATIVE_VALUE_DESC, default=3.4e38)


class Float64(BaseFloat):
    """
    64-bit floating-point datatype.

    Parameters
    ----------
    name : str
        Datatype name. Defaults to ``"FLOAT_64"``.

    type : Literal["float64"]
        Discriminator identifying this datatype.

    bit_size : int
        Storage size in bits. Defaults to 64.

    max_applicative_value : float
        Maximum application-level absolute value allowed.
    """

    name: str = Field(default="FLOAT_64")
    type: Literal["float64"] = Field("float64")  # type: ignore
    bit_size: Annotated[int, Field(ge=33, le=64, default=64)]
    max_applicative_value: Annotated[
        float,
        Field(ge=-1.7976931348623157e308, le=1.7976931348623157e308),
    ] = Field(
        description=BaseFloat.MAX_APPLICATIVE_VALUE_DESC,
        default=1.7976931348623157e308,
    )


class BitfieldEntryValue(BaseModel):
    """
    Represents a named value within a bitfield entry.

    Parameters
    ----------
    value : int
        Numeric value represented by this bitfield entry value.

    name : str
        Symbolic name associated with the value.

    description : str, optional
        Human-readable description of the value.
    """

    value: int = Field()
    name: str = Field()
    description: Optional[str] = Field("", description="Optional description")


class BitfieldEntry(BaseModel):
    """
    Describes a single field within a bitfield.

    Parameters
    ----------
    name : str
        Name of the individual bitfield.

    bitposition : int
        Bit position of the individual bitfield within the enclosing
        bitfield datatype.

    description : str, optional
        Human-readable description of the field.

    values : list of :class:`BitfieldEntryValue`, optional
        Optional enumeration of named values defined for this bitfield
        entry.
    """

    name: str = Field(..., description="Name of the individual bitfield")
    bitposition: int = Field(
        ..., description="Bitposition for the individual bitfield"
    )
    description: Optional[str] = Field(
        "", description="Optional description of the field"
    )
    values: Optional[List[BitfieldEntryValue]] = Field(
        default_factory=list,
        description="Optional values defined for the entry",
    )


class Bitfield(Datatype):
    """
    Allows modeling of SOME/IP bitfields.

    Parameters
    ----------
    name : str
        Unique name of the datatype.

    description : str, optional
        Human-readable description of the datatype.

    type : Literal["bitfield"]
        Discriminator identifying this datatype as a bitfield.

    endianness : Literal["BE", "LE"], optional
        Byte order used for encoding multi-byte values. Defaults to
        big-endian ("BE").

    length : Literal[8, 16, 32, 64], optional
        Size of the bitfield in bits.

    fields : list of :class:`BitfieldEntry`
        List of bitfield entries that define the individual bit ranges.
    """

    type: Literal["bitfield"] = Field("bitfield")

    length: Literal[8, 16, 32, 64] = Field(
        default=8,
        description="defines the possible length of the bitfield",
    )

    fields: Optional[List[BitfieldEntry]] = Field(
        default=None, description="List of bitfield entries"
    )

    @model_validator(mode="after")
    def validate_length_against_fields_size(self):
        """Validate size of fields equals bitfield length"""
        if self.fields is not None and len(self.fields) <= self.length:
            err_minor(
                f"Mismatch between length({self.length}) and "
                f"number of defined fields ({len(self.fields)})"
            )
        return self

    @model_validator(mode="after")
    def validate_bitfieldposition_of_entries(self):
        """Validate bitfield position for all entries must be in range"""
        if self.fields is not None:
            for field in self.fields:
                if field.bitposition < self.length:
                    err_minor(
                        f"Bitposition of {field.name} is out of range: "
                        f"{field.bitposition} >= {self.length}"
                    )
        return self


class EnumEntry(BaseModel):
    """
    Represents a single entry in an enumeration.

    Parameters
    ----------
    value : int
        Numeric value associated with the enumeration entry.

    name : str
        Symbolic name of the enumeration entry.

    description : str, optional
        Human-readable description of the enumeration entry.
    """

    value: int = Field()
    name: str = Field()
    description: str = Field("")


class Enum(Datatype):
    """
    Allows modeling SOME/IP enumerations with value, name, and description.

    Parameters
    ----------
    name : str
        Unique name of the datatype.

    description : str, optional
        Human-readable description of the datatype.

    type : Literal["enum"]
        Datatype discriminator identifying this datatype as an enumeration.

    endianness : Literal["BE", "LE"], optional
        Byte order used for encoding multi-byte values. Defaults to
        big-endian ("BE").

    base_type : Ints, optional
        Underlying integer datatype used to encode enumeration values.
        Defaults to :class:`UInt8`.

    entries : list of :class:`EnumEntry`, optional
        List of enumeration entries defining the mapping between numeric
        values and symbolic names.
    """

    type: Literal["enum"] = Field("enum")
    base_type: Union["Ints"] = Field(
        default_factory=lambda: Enum.default_base_type()
    )
    entries: List[EnumEntry] = Field(default_factory=list)
    BASE_TYPE_RANGES: ClassVar[dict[str, tuple[int, int]]] = {
        "UInt8": (0, 2**8 - 1),
        "UInt16": (0, 2**16 - 1),
        "UInt32": (0, 2**32 - 1),
        "UInt64": (0, 2**64 - 1),
        "SInt8": (-(2**7), 2**7 - 1),
        "SInt16": (-(2**15), 2**15 - 1),
        "SInt32": (-(2**31), 2**31 - 1),
        "SInt64": (-(2**63), 2**63 - 1),
    }

    @field_validator("entries")
    @classmethod
    def validate_entries(
        cls, entries: list["EnumEntry"], info: ValidationInfo
    ) -> list["EnumEntry"]:
        base_type = info.data.get("base_type")
        if base_type is None:
            return entries  # Cannot validate without base_type
        base_type_name = base_type.__class__.__name__
        min_value, max_value = cls.BASE_TYPE_RANGES[base_type_name]
        seen = set()
        for entry in entries:
            if entry.value in seen:
                raise err_minor(f"Duplicate enum value: {entry.value}")
            seen.add(entry.value)
            if not (min_value <= entry.value <= max_value):
                raise err_minor(
                    f"Enum value {entry.value} "
                    f"exceeds valid range for {base_type_name} "
                    f"({min_value} to {max_value})"
                )
        return entries

    @staticmethod
    def default_base_type() -> UInt8:
        return UInt8(type="uint8", endianness="LE", signed=False, bit_size=8)


class BaseString(Datatype):
    """
    Base class for all string datatypes.

    Parameters
    ----------
    type : str
        Discriminator identifying the concrete string type.

    encoding : Literal["UTF-8", "UTF-16BE", "UTF-16LE"]
        Character encoding used for the string payload.
    """

    type: str = Field()
    encoding: Literal["UTF-8", "UTF-16BE", "UTF-16LE"] = Field(
        description="the encoding of the string\n\n"
        ".. needextract::\n"
        '\t:filter: id in ["feat_req_someip_234","feat_req_someip_235"]\n\n',
        default="UTF-8",
    )


class FixedLengthString(BaseString):
    """
    Fixed-length string datatype.

    This string occupies a fixed number of bytes on the wire. If the
    actual content is shorter than the configured length, it is padded
    with zero bytes.

    Parameters
    ----------
    type : Literal["fixed_length_string"]
        Discriminator used to identify this datatype.

    length : int
        Total length of the string in bytes, including zero-termination
        and any padding.

    length_of_length_field : Literal[0, 8, 16, 32]
        Size of the optional length field in bits. A value of 0 indicates
        that no length field is present.
    """

    type: Literal["fixed_length_string"] = Field("fixed_length_string")
    length: Annotated[int, Field(ge=1)] = Field(
        description="the length of the string (including zero-termination!)\n"
        "\n"
        ".. needextract::\n"
        '\t:filter: id in ["feat_req_someip_234"]\n\n'
    )
    length_of_length_field: Literal[0, 8, 16, 32] = Field(
        default=0,
        description="defines the length of the length-field in bits of the"
        "fixed length string where 0 indicates that there is"
        "no length field present.",
    )


class DynamicLengthString(BaseString):
    """
    Dynamic-length string datatype.

    The encoded representation starts with a length field, followed by
    the string content and a zero-termination character.

    Parameters
    ----------
    type : Literal["dynamic_length_string"]
        Discriminator used to identify this datatype.

    length_of_length_field : Literal[8, 16, 32]
        Size of the length field in bits that precedes the string data.

    bit_alignment : Literal[8, 16, 32, 64, 128, 256]
        Optional padding alignment applied after the string so that the
        next parameter starts at the specified bit boundary.
    """

    type: Literal["dynamic_length_string"] = Field(
        default="dynamic_length_string",
        description="used internally by flync to efficiently determine the "
        "constructor to use from yaml",
    )
    length_of_length_field: Literal[8, 16, 32] = Field(
        description="the length of the length field of the string\n\n"
        ".. needextract::\n"
        '\t:filter: id in ["feat_req_someip_237", "feat_req_someip_582", '
        '"feat_req_someip_581"]\n\n',
        default=32,
    )
    bit_alignment: Literal[8, 16, 32, 64, 128, 256] = Field(
        default=8,
        description="defines the optional alignment padding that can be added "
        "after the dynamic length string to fix the alignment of "
        "the next parameter to 8, 16, 32, 64, 128, or 256 bits.",
    )


class ArrayType(ComplexDatatype):
    """
    Generic multidimensional array type.

    Parameters
    ----------
    type : Literal["array"]
        Discriminator identifying this datatype as an array.

    dimensions : List[:class:`ArrayDimension`]
        Ordered list of array dimensions (outer → inner). Must contain
        at least one dimension.

    element_type : :class:`AllTypes`
        Datatype of the innermost array element. This may itself be a
        primitive, struct, union, or another array type.
    """

    type: Literal["array"] = Field("array")
    dimensions: List["ArrayDimension"] = Field(
        min_length=1,
        description="Ordered list of array dimensions (outer → inner)",
    )
    element_type: "AllTypes" = Field(
        description="Datatype of the innermost array element"
    )


class ArrayDimension(FLYNCBaseModel):
    """
    Describes a single array dimension.

    Parameters
    ----------
    kind : Literal["fixed", "dynamic"]
        Specifies whether the dimension has a fixed size or a dynamically
        encoded length.

    length : int, optional
        Number of elements for a fixed-length dimension. Must be greater
        than 0. Only valid when ``kind="fixed"``.

    length_of_length_field : Literal[0, 8, 16, 32], optional
        Size in bits of the length field that precedes the array data for a
        dynamic dimension. Only valid when ``kind="dynamic"``.

    upper_limit : int, optional
        Upper bound on the number of elements. Must be greater than 0.

    lower_limit : int, optional
        Lower bound on the number of elements. Must be greater than or
        equal to 0.

    bit_alignment : Literal[8, 16, 32, 64, 128, 256], optional
        Optional padding alignment in bits applied after this dimension.
    """

    kind: Literal["fixed", "dynamic"]
    # Fixed-length dimension
    length: Optional[int] = Field(
        default=None,
        gt=0,
        description="Number of elements for fixed-length dimension",
    )
    # Dynamic-length dimension
    length_of_length_field: Optional[Literal[0, 8, 16, 32]] = Field(
        default=None,
        description="Length of length-field in bits for dynamic dimension",
    )  # TODO: Validator for dynamic array > 0 and fixed array can be 0
    upper_limit: Optional[int] = Field(
        default=None, gt=0, description="Upper bound of elements"
    )
    lower_limit: Optional[int] = Field(
        default=None, ge=0, description="Lower bound of elements"
    )
    bit_alignment: Optional[Literal[8, 16, 32, 64, 128, 256]] = Field(
        default=None,
        description="Optional padding alignment after this dimension",
    )


class Struct(ComplexDatatype):
    """
    Structured datatype composed of multiple ordered members.

    A struct groups several datatypes into a single composite element that
    is serialized in the order the members are defined.

    Parameters
    ----------
    type : Literal["struct"]
        Discriminator used to identify this datatype.

    members : List[AllTypes]
        Ordered list of datatypes that form the members of the struct.

    bit_alignment : Literal[8, 16, 32, 64, 128, 256]
        Optional padding alignment applied after the struct to ensure the
        next parameter starts at the specified bit boundary.

    length_of_length_field : Literal[0, 8, 16, 32]
        Size of the optional length field in bits that prefixes the struct.
        A value of 0 indicates that no length field is present.
    """

    type: Literal["struct"] = Field("struct")
    members: List["AllTypes"] = Field(
        description="the members of the struct"
    )  # type: ignore
    bit_alignment: Literal[8, 16, 32, 64, 128, 256] = Field(
        default=8,
        description="defines the optional alignment padding that can be added "
        "after the variable length data element like struct to "
        "fix the alignment of the next parameter to 8, 16, 32, "
        "64, 128, or 256 bits.",
    )
    length_of_length_field: Literal[0, 8, 16, 32] = Field(
        default=0,
        description="defines the length of the length-field in bits for "
        "the struct",
    )


class Typedef(ComplexDatatype):
    """
    Alias datatype that references another datatype definition.

    A typedef introduces an alternative name for an existing datatype
    without changing its underlying structure or serialization behavior.

    Parameters
    ----------
    type : Literal["typedef"]
        Discriminator used to identify this datatype.

    name : str
        Name of the typedef reference.

    datatyperef : AllTypes
        Referenced datatype definition that this typedef aliases.
    """

    type: Literal["typedef"] = Field("typedef")
    name: str = Field(description="Name of the typedef reference")
    datatyperef: "AllTypes" = Field(
        description="Referenced datatype definition"
    )  # type: ignore


class UnionMember(Datatype):
    """
    Represents a single member entry of an union datatype.

    Each union member defines a possible datatype that may be present,
    together with its selector index and a descriptive name.

    Parameters
    ----------
    type : AllTypes
        Member datatype (discriminated by its ``type`` field).

    index : int
        Index of the union member. This value is used in the serialized
        union to indicate which member is currently active. Must be
        greater than or equal to 0.

    name : str
        Name of the union member.
    """

    type: Annotated[
        "AllTypes",
        Field(
            description="member datatype (discriminated by its 'type' field)"
        ),
    ]
    index: Annotated[
        int, Field(description="index of the union member", strict=True, ge=0)
    ]
    name: Annotated[str, Field(description="name of the union member")]

    @field_serializer("type")
    def serialize_type(self, type):
        if type is not None:
            return getattr(type, "type", str(type))

    @field_validator("type", mode="before")
    def _wrap_string_type(cls, v):
        if isinstance(v, str):
            s = v.strip().lower()
            return {"type": s}
        return v


class Union(Datatype):
    """
    Represents an union datatype.

    A union allows exactly one of several possible member datatypes to be
    encoded at runtime. The active member is identified using a type
    selector field.

    Parameters
    ----------
    type : Literal["union"]
        Discriminator used to identify this datatype.

    members : list of :class:`UnionMember`
        List of the allowed datatypes a union can contain.

    bit_alignment : Literal[8, 16, 32, 64, 128, 256], optional
        Defines the optional alignment padding that can be added after the
        union to fix the alignment of the next parameter to 8, 16, 32, 64,
        128 or 256 bits.

    length_of_length_field : Literal[0, 8, 16, 32], optional
        Defines the length of the length-field in bits for the union.

    length_of_type_field : Literal[0, 8, 16, 32], optional
        Defines the length of the type-selector field in bits for the union.
    """

    type: Literal["union"] = Field("union")
    members: List[UnionMember] = Field(
        description="list of the allowed datatypes a union can have"
    )
    bit_alignment: Literal[8, 16, 32, 64, 128, 256] = Field(
        default=8,
        description="defines the optional alignment padding that can be \
            added after union to fix the alignment of the next parameter \
                to 8, 16, 32, 64, 128 or 256 bits.",
    )
    length_of_length_field: Literal[0, 8, 16, 32] = Field(
        default=32,
        description="defines the length of the length-field \
            in bits for the union",
    )
    length_of_type_field: Literal[0, 8, 16, 32] = Field(
        default=32,
        description="defines the length of the type-selector-field \
            in bits for the union",
    )


SignedInts = Annotated[
    SInt8 | SInt16 | SInt32 | SInt64,
    Field(discriminator="type"),
]
"Collection of Signed Integer Types"

UnsignedInts = Annotated[
    UInt8 | UInt16 | UInt32 | UInt64,
    Field(discriminator="type"),
]
"Collection of Unsigned Integer Types"

Ints = Annotated[
    SignedInts | UnsignedInts,
    Field(discriminator="type"),
]
"Collection of Integer Types"

Floats = Annotated[
    Float32 | Float64,
    Field(discriminator="type"),
]
"Collection of Float Types"

AllTypes = Annotated[
    Ints
    | Floats
    | Enum
    | Boolean
    | Struct
    | Union
    | ArrayType
    | DynamicLengthString
    | FixedLengthString
    | Bitfield,
    Field(discriminator="type"),
]
"Collection of all dataypes"
