"""defines string datatypes"""

from typing import Annotated, Literal

from pydantic import Field

from .base import Datatype


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


__all__ = ["DynamicLengthString", "FixedLengthString"]
