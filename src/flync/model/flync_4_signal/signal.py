from enum import Enum
from typing import List, Literal, Optional

from pydantic import Field, field_serializer, field_validator, model_validator

from flync.core.base_models import FLYNCBaseModel, UniqueName


class SignalDataType(str, Enum):
    """
    Supported signal base data types for CAN, LIN, FlexRay, and Ethernet.
    """

    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    CHAR = "char"
    BYTEARRAY = "bytearray"

    def natural_bit_width(self) -> Optional[int]:
        """Canonical bit width for this type. Size for single element for ``char`` and ``bytearray``."""
        _widths = {
            SignalDataType.UINT8: 8,
            SignalDataType.UINT16: 16,
            SignalDataType.UINT32: 32,
            SignalDataType.UINT64: 64,
            SignalDataType.INT8: 8,
            SignalDataType.INT16: 16,
            SignalDataType.INT32: 32,
            SignalDataType.INT64: 64,
            SignalDataType.FLOAT32: 32,
            SignalDataType.FLOAT64: 64,
            SignalDataType.CHAR: 8,
            SignalDataType.BYTEARRAY: 8,
        }
        return _widths.get(self)

    def is_float(self) -> bool:
        """Return ``True`` for float types (``float32``, ``float64``)."""
        return self in (SignalDataType.FLOAT32, SignalDataType.FLOAT64)

    def is_unsigned_integer(self) -> bool:
        """Return ``True`` for unsigned integer types."""
        return self in (
            SignalDataType.UINT8,
            SignalDataType.UINT16,
            SignalDataType.UINT32,
            SignalDataType.UINT64,
        )

    def is_signed_integer(self) -> bool:
        """Return ``True`` for signed integer types."""
        return self in (
            SignalDataType.INT8,
            SignalDataType.INT16,
            SignalDataType.INT32,
            SignalDataType.INT64,
        )

    def is_complex_datattype(self) -> bool:
        """Return ``True`` for complex datatypes."""
        return self in (
            SignalDataType.CHAR,
            SignalDataType.BYTEARRAY,
        )


class ValueDescription(FLYNCBaseModel):
    """
    Mapping from a raw integer value to a human-readable label.

    Parameters
    ----------
    value : int
        The raw integer value of the signal.
    description : str
        Human-readable label for this value (e.g. ``"Off"``,
        ``"Active"``).
    """

    value: int = Field()
    description: str = Field()


class InstancePlacement(FLYNCBaseModel):
    """
    Shared placement metadata for signal and signal-group instances within
    a PDU.

    Parameters
    ----------
    bit_position : int, optional
        Non-negative bit offset in the PDU.
    update_indication_bit_position : int, optional
        Bit position used to indicate that the value has been updated.
    endianness : Literal["BE", "LE"]
        Byte order for this instance.  Defaults to ``"little_endian"``.
    subscriber_nodes : list of str
        Names of the nodes that receive this signal or group.
    """

    bit_position: Optional[int] = Field(default=None, ge=0)
    update_indication_bit_position: Optional[int] = Field(default=None)
    endianness: Literal["BE", "LE"] = Field(default="LE")
    subscriber_nodes: List[str] = Field(default_factory=list)


class Signal(UniqueName):
    """
    Logical or physical data element transmitted within a communication
    message.

    Parameters
    ----------
    name : str
        Unique name of the signal.
    description : str, optional
        Optional textual description of the signal.
    bit_length : int
        Length of the signal in bits.
    data_type : :class:`SignalDataType`
        Base data type of the signal.
    factor : float
        Multiplication factor applied to the raw value to obtain the
        physical value.  Defaults to ``1.0``.
    offset : float
        Additive offset applied after scaling to obtain the physical
        value.  Defaults to ``0.0``.
    lower_limit : float, optional
        Minimum physical value of the signal.
    upper_limit : float, optional
        Maximum physical value of the signal.
    unit : str, optional
        Physical unit of the signal (e.g. ``"km/h"``, ``"°C"``).
    initial_value : float | int | bytes | str, optional
        Optional initial value of the signal at startup.
    value_descriptions : list of :class:`ValueDescription`
        Discrete value-to-label mappings for enumerated signals.
    """

    name: str = Field()
    description: Optional[str] = Field(default=None)
    bit_length: int = Field(gt=0)
    data_type: SignalDataType = Field()
    factor: float = Field(default=1.0)
    offset: float = Field(default=0.0)
    lower_limit: Optional[float] = Field(default=None)
    upper_limit: Optional[float] = Field(default=None)
    unit: Optional[str] = Field(default=None)
    initial_value: Optional[float | int | bytes | str] = Field(default=None)
    value_descriptions: List[ValueDescription] = Field(default_factory=list)

    @field_serializer("data_type")
    def serialize_data_type(self, data_type: SignalDataType) -> str:
        return data_type.value

    @field_validator("factor")
    @classmethod
    def _factor_nonzero(cls, v: float) -> float:
        """Reject a zero factor, which would collapse all physical values."""
        if not v:
            raise ValueError("factor must not be zero; a zero factor collapses all physical values to the offset")
        return v

    @field_validator("value_descriptions")
    @classmethod
    def _value_descriptions_unique(cls, v: List[ValueDescription]) -> List[ValueDescription]:
        seen: set[int] = set()
        for vd in v:
            if vd.value in seen:
                raise ValueError(f"Duplicate value {vd.value!r} in value_descriptions; each raw value must appear at most once")
            seen.add(vd.value)
        return v

    @model_validator(mode="after")
    def _validate_bit_length_for_data_type(self) -> "Signal":
        natural = self.data_type.natural_bit_width()
        if self.data_type.is_complex_datattype():
            if natural is not None and (self.bit_length < natural or self.bit_length % natural != 0):
                raise ValueError(f"{self.data_type.value} requires {natural} bits or a multiple of that; got bit_length={self.bit_length}")
            return self
        elif self.data_type.is_float():
            if self.bit_length != natural:
                raise ValueError(f"{self.data_type.value} requires exactly {natural} bits; got bit_length={self.bit_length}")
        elif natural is not None and self.bit_length > natural:
            raise ValueError(f"bit_length={self.bit_length} exceeds the natural width of {self.data_type.value} ({natural} bits)")
        return self

    @model_validator(mode="after")
    def _validate_limits(self) -> "Signal":
        if self.lower_limit is not None and self.upper_limit is not None:
            if self.lower_limit > self.upper_limit:
                raise ValueError(f"lower_limit ({self.lower_limit}) must not exceed upper_limit ({self.upper_limit})")
        return self

    @model_validator(mode="after")
    def _validate_initial_value(self) -> "Signal":
        if self.initial_value is not None:
            _check_initial_value(self.initial_value, self.data_type, self.bit_length)
        return self

    @model_validator(mode="after")
    def _validate_value_descriptions_range(self) -> "Signal":
        dt = self.data_type
        if self.value_descriptions and not (dt.is_float() or dt in (SignalDataType.CHAR, SignalDataType.BYTEARRAY)):
            if dt.is_unsigned_integer():
                lo, hi = 0, (1 << self.bit_length) - 1
            else:
                lo = -(1 << (self.bit_length - 1))
                hi = (1 << (self.bit_length - 1)) - 1
            for vd in self.value_descriptions:
                if not (lo <= vd.value <= hi):
                    raise ValueError(
                        f"ValueDescription.value {vd.value} is outside the "
                        f"representable range [{lo}, {hi}] for {dt.value} "
                        f"with bit_length={self.bit_length}"
                    )
        return self


class SignalInstance(InstancePlacement):
    """
    Placement of a :class:`Signal` at a specific bit offset within a PDU.

    Parameters
    ----------
    signal : :class:`Signal`
        Signal being instantiated.
    """

    signal: Signal = Field()


class SignalGroup(UniqueName):
    """
    A reusable group of signals transmitted together within a PDU.

    Parameters
    ----------
    name : str
        Unique name of the signal group.
    description : str, optional
        Optional textual description of the group.
    signals : list of :class:`Signal`
        Non-empty list of signal definitions contained in this group.
    """

    name: str = Field()
    description: Optional[str] = Field(default=None)
    signals: List[Signal] = Field(min_length=1)


class SignalGroupInstance(InstancePlacement):
    """
    Placement of a :class:`SignalGroup` at a specific bit offset within a PDU.

    Parameters
    ----------
    signal_group : :class:`SignalGroup`
        Signal group being instantiated.
    """

    signal_group: SignalGroup = Field()


def _check_initial_value(iv: object, dt: SignalDataType, bit_length: int) -> None:
    """Validate if the type is fit or not."""
    if dt == SignalDataType.BYTEARRAY:
        if not isinstance(iv, bytes):
            raise ValueError(f"initial_value for bytearray signal must be bytes; got {type(iv).__name__}")
    elif dt == SignalDataType.CHAR:
        if not isinstance(iv, str):
            raise ValueError(f"initial_value for char signal must be str; got {type(iv).__name__}")
    elif dt.is_float():
        if not isinstance(iv, (float, int)) or isinstance(iv, bool):
            raise ValueError(f"initial_value for {dt.value} must be numeric; got {type(iv).__name__}")
    elif dt.is_unsigned_integer() or dt.is_signed_integer():
        _check_integer_initial_value(iv, dt, bit_length)


def _check_integer_initial_value(iv: object, dt: SignalDataType, bit_length: int) -> None:
    """Validate that an integer is the right type and fits in bit_length."""
    if not isinstance(iv, int) or isinstance(iv, bool):
        raise ValueError(f"initial_value for {dt.value} must be int; got {type(iv).__name__}")
    if dt.is_unsigned_integer():
        lo, hi = 0, (1 << bit_length) - 1
    else:
        lo = -(1 << (bit_length - 1))
        hi = (1 << (bit_length - 1)) - 1
    if not (lo <= iv <= hi):
        raise ValueError(f"initial_value {iv} is outside the representable range [{lo}, {hi}] for {dt.value} with bit_length={bit_length}")
