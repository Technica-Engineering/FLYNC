from collections import Counter
from typing import Annotated, List, Optional, Union

from pydantic import Field, field_validator, model_validator

from flync.core.base_models import UniqueName
from flync.core.utils.exceptions import err_major, err_minor
from flync.model.flync_4_signal.frame import CANFDFrame, CANFrame

_ALLOWED_CAN_BAUD_RATES = frozenset(
    {
        10_000,
        20_000,
        50_000,
        100_000,
        125_000,
        250_000,
        500_000,
        1_000_000,
    }
)

_ALLOWED_CAN_FD_DATA_RATES = frozenset(
    {
        2_000_000,
        4_000_000,
        5_000_000,
        8_000_000,
    }
)


class CANBus(UniqueName):
    """
    CAN bus configuration.

    Parameters
    ----------
    name : str
        Unique name of the CAN bus.
    description : str, optional
        Optional human-readable description.
    version : str
        Version string.  Defaults to ``""``.
    baud_rate : int
        Nominal bit rate in bits/s.  Must be one of: 10 000, 20 000, 50 000, 100 000, 125 000, 250 000, 500 000, or 1 000 000.
    fd_enabled : bool
        Whether CAN FD is enabled on this bus.  Defaults to ``False``.
    fd_baud_rate : int, optional
        Data-phase bit rate in bits/s.  Required when ``fd_enabled`` is ``True``; must be ``None`` otherwise.  Must be one of: 2 000 000,
        4 000 000, 5 000 000, or 8 000 000.
    frames : list of :class:`CANFrame` | :class:`CANFDFrame`
        Frames transmitted on this bus.  :class:`CANFDFrame` entries are only permitted when ``fd_enabled`` is ``True``.
    """

    name: str = Field()
    description: Optional[str] = Field(default=None)
    version: str = Field(default="", max_length=128, pattern=r'^[^"\r\n]*$')
    baud_rate: int = Field()
    fd_enabled: bool = Field(default=False)
    fd_baud_rate: Optional[int] = Field(default=None)
    frames: List[Annotated[Union[CANFrame, CANFDFrame], Field(discriminator="type")]] = Field(default_factory=list)

    @field_validator("baud_rate")
    @classmethod
    def validate_baud_rate(cls, value: int) -> int:
        if value not in _ALLOWED_CAN_BAUD_RATES:
            raise err_minor(
                "baud_rate {value} is not a valid CAN baud rate. Allowed values: {allowed}",
                value=value,
                allowed=sorted(_ALLOWED_CAN_BAUD_RATES),
            )
        return value

    @model_validator(mode="after")
    def validate_fd_configuration(self) -> "CANBus":
        if self.fd_enabled and self.fd_baud_rate is None:
            raise err_major(
                "CANBus '{name}': fd_baud_rate must be set when fd_enabled is True",
                name=self.name,
            )
        if not self.fd_enabled and self.fd_baud_rate is not None:
            raise err_major(
                "CANBus '{name}': fd_baud_rate must be None when fd_enabled is False",
                name=self.name,
            )
        if self.fd_baud_rate is not None and self.fd_baud_rate not in _ALLOWED_CAN_FD_DATA_RATES:
            raise err_minor(
                "CANBus '{name}': fd_baud_rate {value} is not a standard CAN FD data-phase rate. Allowed values: {allowed}",
                name=self.name,
                value=self.fd_baud_rate,
                allowed=sorted(_ALLOWED_CAN_FD_DATA_RATES),
            )
        return self

    @model_validator(mode="after")
    def validate_can_fd_frames_require_fd_enabled(self) -> "CANBus":
        if not self.fd_enabled:
            fd_frames = [f.name for f in self.frames if isinstance(f, CANFDFrame)]
            if fd_frames:
                raise err_major(
                    "CANBus '{name}' has CANFDFrame(s) {fd_frames} but fd_enabled is False",
                    name=self.name,
                    fd_frames=fd_frames,
                )
        return self

    @model_validator(mode="after")
    def validate_unique_frame_names(self) -> "CANBus":
        duplicates = sorted(n for n, c in Counter(f.name for f in self.frames).items() if c > 1)
        if duplicates:
            raise err_minor(
                "CANBus '{name}' has duplicate frame name(s): {duplicates}",
                name=self.name,
                duplicates=duplicates,
            )
        return self

    @model_validator(mode="after")
    def validate_unique_can_ids(self) -> "CANBus":
        keys = [(f.can_id, f.id_format) for f in self.frames]
        duplicates = sorted(f"{cid:#x}/{fmt}" for (cid, fmt), c in Counter(keys).items() if c > 1)
        if duplicates:
            raise err_major(
                "CANBus '{name}' has duplicate CAN identifier(s): {duplicates}",
                name=self.name,
                duplicates=duplicates,
            )
        return self
