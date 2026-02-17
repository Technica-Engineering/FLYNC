from typing import Literal, Optional

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class BASET1(FLYNCBaseModel):
    """
    Represents a BASE-T1 Ethernet interface configuration.

    Parameters
    ----------
    mode : Literal["base_t1"]
        Interface mode. Defaults to ``"base_t1"``.

    speed : int
        Supported link speed in megabits per second. Valid values are
        100 or 1000.

    duplex : Literal["full"]
        Duplex mode. Defaults to ``"full"``.

    role : Literal["master", "slave"]
        Role of the PHY, either master or slave.

    autonegotiation : bool
        Indicates whether autonegotiation is enabled.
    """

    mode: Literal["base_t1"] = Field(default="base_t1")
    speed: Literal[100, 1000] = Field(default=100)
    duplex: Literal["full"] = Field(default="full")
    role: Literal["master", "slave"] = Field(default="slave")
    autonegotiation: bool = Field(default=False)


class BASET1S(FLYNCBaseModel):
    """
    Represents a BASE-T1S Ethernet interface configuration.

    Parameters
    ----------
    mode : Literal["base_t1s"]
        Interface mode. Defaults to ``"base_t1s"``.

    speed : int
        Supported link speed in megabits per second. Defaults to 10.

    duplex : Literal["half"]
        Duplex mode. Defaults to ``"half"``.

    role : Literal["master", "slave"]
        Role of the PHY, either master or slave.

    autonegotiation : bool
        Indicates whether autonegotiation is enabled.
    """

    mode: Literal["base_t1s"] = Field(default="base_t1s")
    speed: Literal[10] = Field(default=10)
    duplex: Literal["half"] = Field(default="half")
    role: Literal["master", "slave"] = Field()
    autonegotiation: bool = Field(default=False)


class BASET(FLYNCBaseModel):
    """
    Represents a BASE-T Ethernet interface configuration.

    Parameters
    ----------
    mode : Literal["base_t"]
        Interface mode. Defaults to ``"base_t"``.

    speed : int
        Supported link speed in megabits per second. Valid values are
        100 or 1000.

    duplex : Literal["full"]
        Duplex mode. Defaults to ``"full"``.

    autonegotiation : bool
        Indicates whether autonegotiation is enabled.
    """

    mode: Literal["base_t"] = Field(default="base_t")
    speed: Literal[100, 1000] = Field()
    duplex: Literal["full"] = Field(default="full")
    autonegotiation: bool = Field(default=False)


class MII(FLYNCBaseModel):
    """
    Represents a Media Independent Interface (MII) configuration.

    Parameters
    ----------
    type : Literal["mii"]
        Interface type. Defaults to ``"mii"``.

    speed : int
        Supported link speed in megabits per second. Valid values are
        10 or 100.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["mii"] = Field(default="mii")
    speed: Optional[Literal[10, 100]] = Field(default=100)
    mode: Literal["mac", "phy"] = Field()


class RMII(FLYNCBaseModel):
    """
    Represents a Reduced Media Independent Interface (RMII)
    configuration.

    Parameters
    ----------
    type : Literal["rmii"]
        Interface type. Defaults to ``"rmii"``.

    speed : int
        Supported link speed in megabits per second. Valid values are
        10 or 100.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["rmii"] = Field(default="rmii")
    speed: Optional[Literal[10, 100]] = Field(default=100)
    mode: Literal["mac", "phy"] = Field()


class SGMII(FLYNCBaseModel):
    """
    Represents a Serial Gigabit Media Independent Interface
    (SGMII or SGMII+) configuration.

    Parameters
    ----------
    type : Literal["sgmii"]
        Interface type. Defaults to ``"sgmii"``.

    speed : int
        Supported link speed in megabits per second. Valid values are 10,
        100, 1000, or 2500. Defaults to 1000 Mbps.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["sgmii"] = Field(default="sgmii")
    speed: Optional[Literal[10, 100, 1000, 2500]] = Field(default=1000)
    mode: Literal["mac", "phy"] = Field()


class RGMII(FLYNCBaseModel):
    """
    Represents a Reduced Gigabit Media Independent Interface (RGMII)
    configuration.

    Parameters
    ----------
    type : Literal["rgmii"]
        Interface type. Defaults to ``"rgmii"``.

    speed : int
        Supported link speed in megabits per second. Valid values are 10,
        100, or 1000. Defaults to 1000 Mbps.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["rgmii"] = Field(default="rgmii")
    speed: Optional[Literal[10, 100, 1000]] = Field(default=1000)
    mode: Literal["mac", "phy"] = Field()


class XFI(FLYNCBaseModel):
    """
    Represents a 10-Gigabit Ethernet (10GbE) serial electrical interface
    (XFI) configuration.

    Parameters
    ----------
    type : Literal["xfi"]
        Interface type. Defaults to "xfi".

    speed : Literal[10000]
        Supported speed in Mbps. Defaults to 10000.

    mode : Literal["mac", "phy"]
        Operating mode of the interface, either MAC or PHY.
    """

    type: Literal["xfi"] = Field(default="xfi")
    speed: Literal[10000] = Field(default=10000)
    mode: Literal["mac", "phy"] = Field()
