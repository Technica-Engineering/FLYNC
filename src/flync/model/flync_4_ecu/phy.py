"""
Defines the supported physical layer (PHY) interface
configurations used in the FLYNC model
"""

from typing import TYPE_CHECKING, Literal, Optional, Self

from pydantic import Field, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, warn

# breaking circular import dependency
if TYPE_CHECKING:  # pragma: no cover
    from flync.model.flync_4_topology.ethernet_multidrop import EthernetMultidropNode


class BASET1(FLYNCBaseModel):
    """
    Represents a BASE-T1 Ethernet interface configuration.

    Parameters
    ----------
    mode : Literal["base_t1"]
        Interface mode. Defaults to ``"base_t1"``.

    speed : int
        Supported link speed in megabits per second. Valid values are 100 or 1000.

    duplex : Literal["full"]
        Duplex mode. Defaults to ``"full"``.

    role : Literal["master", "slave"]
        Role of the PHY, either master or slave.

    autonegotiation : bool, optional
        Indicates whether autonegotiation is enabled (defaults to ``False``).
    """

    mode: Literal["base_t1"] = Field(default="base_t1")
    speed: Literal[100, 1000] = Field(default=100)
    duplex: Literal["full"] = Field(default="full")
    role: Literal["master", "slave"] = Field(default="slave")
    autonegotiation: bool = Field(default=False)


class BASET1S(FLYNCBaseModel):
    """
    10BASE-T1S PHY, IEEE 802.3-2022 Clause 147.

    Half duplex on a shared multidrop segment (with PLCA) or full duplex on a point-to-point link.

    There is no ``role`` field.  DME is self-clocked, so no side of the link supplies a clock; a config that still sets ``role``
    loads with a warning and drops the key.

    Parameters
    ----------
    mode : Literal["base_t1s"]
        Interface mode. Defaults to ``"base_t1s"``.

    speed : int
        Link speed in megabits per second. Defaults to 10.

    duplex : Literal["half", "full"]
        Duplex mode. Defaults to ``"half"``.  ``"full"`` is valid only with ``topology="p2p"``: a shared medium is always half duplex.

    topology : Literal["p2p", "multidrop"]
        Whether the PHY sits on a point-to-point link or a shared multidrop segment. Defaults to ``"p2p"``.

    autonegotiation : bool, optional
        Autonegotiation enabled (defaults to ``False``).  Valid on a point-to-point link only: a mixing segment is shared, so there is
        no peer to negotiate with.

    """

    mode: Literal["base_t1s"] = Field(default="base_t1s")
    speed: Literal[10] = Field(default=10)
    duplex: Literal["half", "full"] = Field(default="half")
    topology: Literal["p2p", "multidrop"] = Field(default="p2p")
    autonegotiation: bool = Field(default=False)

    _multidrop_node: Optional["EthernetMultidropNode"] = None

    @property
    def node_id(self) -> Optional[int]:
        """This port's slot in the PLCA cycle, 0 to 254; 0 makes it the coordinator."""

        node = self._multidrop_node
        return node.node_id if node is not None else None

    @property
    def burst_count(self) -> Optional[int]:
        """Extra frames this port may send back-to-back in its slot, besides the slot's own."""

        node = self._multidrop_node
        return node.burst_count if node is not None else None

    @property
    def burst_timer(self) -> Optional[int]:
        """How long this port may hold the medium between burst frames, in bit times; reflected, or ``None`` while unbound."""

        node = self._multidrop_node
        return node.burst_timer if node is not None else None

    @property
    def role(self) -> Optional[str]:
        """This port's part in the cycle, mirroring the node's: ``"coordinator"`` for slot 0, ``"follower"`` otherwise, ``None`` without a slot."""

        node = self._multidrop_node
        return node.role if node is not None else None

    @model_validator(mode="before")
    @classmethod
    def drop_legacy_role(cls, data: object) -> object:
        """Drop a ``role`` left over from an earlier FLYNC version, with a warning."""

        if not isinstance(data, dict) or "role" not in data:
            return data

        warn(
            f"10BASE-T1S MDI config declares 'role' ({data['role']!r}), which FLYNC no longer models and ignores.",
            category=Category.LIFECYCLE,
            error_number="338",
        )
        return {key: value for key, value in data.items() if key != "role"}

    @model_validator(mode="after")
    def validate_topology_consistency(self) -> Self:
        """Duplex and autonegotiation both need two peers on a link, which a shared medium does not have."""

        if self.topology == "multidrop":
            if self.duplex == "full":
                raise err_major(
                    "10BASE-T1S PHY declares duplex 'full' on topology '{topology}'. A shared multidrop segment has to be half duplex.",
                    topology=self.topology,
                    category=Category.CONSISTENCY,
                    error_number="324",
                )

            if self.autonegotiation:
                raise err_major(
                    "10BASE-T1S PHY on a multidrop segment does not support autonegotiation. Available in 'p2p' only.",
                    category=Category.CONSISTENCY,
                    error_number="319",
                )

        return self


class BASET(FLYNCBaseModel):
    """
    Represents a BASE-T Ethernet interface configuration.

    Parameters
    ----------
    mode : Literal["base_t"]
        Interface mode. Defaults to ``"base_t"``.

    speed : int
        Supported link speed in megabits per second. Valid values are 100 or 1000.

    duplex : Literal["full"]
        Duplex mode. Defaults to ``"full"``.

    role : Literal["master", "slave"]
        Role of the PHY, either master or slave. Defaults to ``"slave"``.

    autonegotiation : bool, optional
        Indicates whether autonegotiation is enabled (defaults to ``False``).
    """

    mode: Literal["base_t"] = Field(default="base_t")
    speed: Literal[100, 1000] = Field()
    duplex: Literal["full"] = Field(default="full")
    role: Literal["master", "slave"] = Field(default="slave")
    autonegotiation: bool = Field(default=False)
