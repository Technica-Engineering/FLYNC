from typing import Annotated

from pydantic import AfterValidator, ConfigDict, Field
from pydantic_extra_types.mac_address import MacAddress

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.common_validators import (
    validate_mac_multicast,
    validate_mac_unicast,
)
from flync.core.annotations.hint import Hint, HintStrategy


class MACAddressEntry(FLYNCBaseModel):
    """
    Represents an MAC address entry for a network interface.

    Parameters:
        - address (str):
            Source MAC address to filter by. Format: "xx:xx:xx:xx:xx:xx"
        - macmask (str):
            The mask in MAC format. Format: "xx:xx:xx:xx:xx:xx"
    """

    model_config = ConfigDict(extra="forbid")
    address: MacAddress = Field()
    macmask: Annotated[
        str, Hint(value="FF:FF:FF:FF:FF:FF", hint_strategy=HintStrategy.FIXED)
    ] = Field()


class UnicastMACAddressEntry(MACAddressEntry):
    """
    Represents a Unicast MAC address entry for a network interface.
    """

    address: Annotated[
        MacAddress,
        AfterValidator(validate_mac_unicast),
        Hint(value="AA:AA:AA:AA:AA:AA", hint_strategy=HintStrategy.FIXED),
    ] = Field()


class MulticastMACAddressEntry(MACAddressEntry):
    """
    Represents a Multicast MAC address entry for a network interface.
    """

    address: Annotated[
        MacAddress,
        AfterValidator(validate_mac_multicast),
    ] = Field()
