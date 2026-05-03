"""Defines MACsec configuration for FLYNC."""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import AfterValidator, Field, model_validator

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.common_validators import validate_vlan_id
from flync.core.utils.exceptions import err_minor


class IntegrityWithoutConfidentiality(FLYNCBaseModel):
    """
    Cipher configuration representing integrity protection without confidentiality.

    This configuration supports authentication and integrity checks but does not encrypt the data.

    Parameters
    ----------
    type : Literal["integrity_without_confidentiality"]
        Identifier for the cipher type. Always ``"integrity_without_confidentiality"``.

    offset_preference : Literal[0]
        Preference for offset timing. Always 0 for this cipher.
    """

    type: Literal["integrity_without_confidentiality"] = Field(default="integrity_without_confidentiality")
    offset_preference: Optional[Literal[0]] = Field(default=0)


class IntegrityWithConfidentiality(FLYNCBaseModel):
    """
    Cipher configuration representing both integrity protection and confidentiality.

    This configuration includes both encryption and authentication features.

    Parameters
    ----------
    type : Literal["integrity_with_confidentiality"]
        Identifier for the cipher type.
        Always ``"integrity_with_confidentiality"``.

    offset_preference : Literal[0, 30, 50]
        Offset timing preference for transmission (in nanoseconds).
        Allows choosing between no offset, 30 ns, or 50 ns.
    """

    type: Literal["integrity_with_confidentiality"] = Field(default="integrity_with_confidentiality")
    offset_preference: Optional[Literal[0, 30, 50]] = Field(default=0)


DiscriminatedCipher = Annotated[
    Union["IntegrityWithoutConfidentiality", "IntegrityWithConfidentiality"],
    Field(discriminator="type"),
]


class MACsecConfig(FLYNCBaseModel):
    """
    Configuration for MACsec (Media Access Control Security).

    Includes global MKA (MACsec Key Agreement) settings and per-port security configuration.

    Parameters
    ----------
    vlan_bypass : list of int
        VLANs which shall not be protected with MACsec.

    mka_enabled : bool
        Whether MACsec Key Agreement (MKA) is enabled. Default is True.

    hello_time : int
        MKPDU period when a connection is established, applicable when delay_protect is disabled (milliseconds).

    bounded_hello_time : int
        Hello time applicable with delay_protect enabled (milliseconds).

    life_time : int
        Life time for a peer to transmit MKPDU's in order to consider it alive (milliseconds).

    sak_retire_time : int
        During a key rotation, time to retire the previous SAK key (milliseconds).

    hello_time_rampup : list of int
        Periods between initial MKA messages after linkup (milliseconds).

    sak_rekey_time : int
        Minimum interval (in seconds) before rekeying the SAK.

    macsec_mode : Literal["disabled", "integrity", \
    "integrity_confidentiality"]
        MACsec operation mode. Options include disabled, integrity-only, and full encryption.

    kay_on : bool
        Whether to activate the KaY (Key Agreement Entity) module.
        When disabled, MACsec is not negotiated.

    key_role : Literal["key_server_always", "key_server_never"]
        Role of the device in key negotiation.

    delay_protect : bool
        When enabled, performs frequent updates of the packet number on the receiving side to prevent attackers from delaying MACsec frames.

    participant_activation : Literal["disabled", "onoperup", "always"]
        Strategy for participant activation.

    sci_included : bool
        Whether to include the Secure Channel Identifier (SCI) in MACsec frames.

    cipher_preference : list of :class:`DiscriminatedCipher`
        List of preferred ciphers to negotiate, ordered by priority.
        Defaults to using integrity-only without confidentiality.
    """

    vlan_bypass: List[Annotated[int, Field(ge=1), AfterValidator(validate_vlan_id)]] = Field()
    mka_enabled: Optional[bool] = Field(default=True)
    hello_time: int = Field()
    bounded_hello_time: int = Field()
    life_time: int = Field()
    sak_retire_time: int = Field()
    hello_time_rampup: List[int] = Field([])
    sak_rekey_time: Optional[int] = Field(default=3, ge=0)
    macsec_mode: Literal["disabled", "integrity", "integrity_confidentiality"] = Field()
    kay_on: bool = Field()
    key_role: Literal["key_server_always", "key_server_never"] = Field()
    delay_protect: bool = Field()
    participant_activation: Literal["disabled", "onoperup", "always"] = Field()
    sci_included: Optional[bool] = Field(default=False)
    cipher_preference: List[DiscriminatedCipher] = Field(default_factory=lambda: MACsecConfig.default_entries_list())

    @model_validator(mode="after")
    def validate_mka_macsecmode_disabled(self):
        if not self.mka_enabled and self.macsec_mode != "disabled":
            raise err_minor("If MKA is not enabled, macsec_mode should be disabled.")
        return self

    @model_validator(mode="after")
    def validate_life_time_greater_than_hello_time(self):
        if self.life_time < self.hello_time:
            raise err_minor("Life time should be greater than hello time.")
        return self

    @staticmethod
    def default_entries_list() -> list[IntegrityWithoutConfidentiality | IntegrityWithConfidentiality]:
        entries: list[IntegrityWithoutConfidentiality | IntegrityWithConfidentiality] = [IntegrityWithoutConfidentiality()]
        return entries
