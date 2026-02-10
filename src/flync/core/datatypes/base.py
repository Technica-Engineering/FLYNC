"""defines the base class each datatype shares"""

from typing import Literal, Optional

from pydantic import ConfigDict, Field

from flync.core.base_models.base_model import FLYNCBaseModel


class Datatype(FLYNCBaseModel):
    """
    Base class of every datatype.

    Parameters
    ----------
    name : str
        Unique name of the datatype.

    description : str, optional
        Human-readable description of the datatype.

    type : str
        Discriminator identifying the concrete datatype kind.

    endianness : Literal["BE", "LE"], optional
        Byte order used for encoding multi-byte values. Defaults to
        big-endian ("BE").
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field()
    description: Optional[str] = Field(default="")
    type: str | object = Field()
    endianness: Literal["BE", "LE"] = Field("BE")
