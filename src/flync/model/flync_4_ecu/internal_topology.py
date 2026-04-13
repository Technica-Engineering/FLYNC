"""
Defines the internal connection types between ECU components
such as ECU ports, switch ports, and controller interfaces.
"""

from typing import TYPE_CHECKING, Annotated, List, Literal, Optional

from pydantic import Field, PrivateAttr, RootModel, model_validator

import flync.core.utils.common_validators as common_validators
from flync.core.annotations.reference import Reference
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import err_major
from flync.model.flync_4_ecu.controller import ControllerInterface
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.ecu import ECU


class InternalConnection(FLYNCBaseModel):
    """
    Represents a base internal connection between two
    ECU components.

    Parameters
    ----------
    type : str
        The type of the connection.

    id : str
        Unique identifier for the connection.

    component1_name : str, optional
        Name of the first component in the connection.

    component2_name : str, optional
        Name of the second component in the connection.

    Private Attributes
    ------------------
    _ecu : :class:`~flync.model.flync_4_ecu.ecu.ECU`
        The ECU object to which this connection belongs.
        Managed internally.
    """

    type: str = Field()
    id: str = Field()
    _ecu: Optional["ECU"] = PrivateAttr(default=None)

    @property
    def ecu(self) -> Optional["ECU"]:
        return self._ecu


class ECUPortToXConnection(InternalConnection):
    """
    Base class for connections from an ECU port to another
    ECU component.

    Parameters
    ----------
    ecu_port_name : str
        Name of the ECU port (alias: ``ecu_port``).

    Private Attributes
    ------------------
    _ecu_port : :class:`~flync.model.flync_4_ecu.port.ECUPort`
        Internal reference to the actual ECU port object.
        Managed privately.
    """

    ecu_port_name: Annotated[str, Reference(source="_ecu_port")] = Field(
        alias="ecu_port"
    )
    _ecu_port: Optional["ECUPort"] = PrivateAttr(default=None)

    @property
    def ecu_port(self) -> Optional["ECUPort"]:
        return self._ecu_port

    @model_validator(mode="after")
    def validate_ecu_port_exists(self):
        """Check if the ECU port referenced by the connection exists.

        Raises:
            err_major: No matching ECU port found for the connection.
        """
        if self.ecu_port_name not in ECUPort.INSTANCES.keys():
            raise err_major(
                f"ECU port name {self.ecu_port_name} in connection"
                f" {self.id} does not exist"
            )
        self._ecu_port = ECUPort.INSTANCES[self.ecu_port_name]
        return self


class SwitchPortToXConnection(InternalConnection):
    """
    Base class for connections from an ECU switch port to another component.

    Parameters
    ----------
    switch_port_name : str
        Name of the ECU switch port (alias: ``switch_port``).

    Private Attributes
    ------------------
    _switch_port : :class:`~flync.model.flync_4_ecu.switch.SwitchPort`
        Internal reference to the actual switch port object.
        Managed privately.
    """

    switch_port_name: Annotated[str, Reference(source="_switch_port")] = Field(
        alias="switch_port"
    )
    _switch_port: "SwitchPort" = PrivateAttr()

    @property
    def switch_port(self) -> "SwitchPort":
        return self._switch_port

    @model_validator(mode="after")
    def validate_switch_port_exists(self):
        """Check if the switch port referenced by the connection exists.

        Raises:
            err_major: No matching switch port found for the connection.
        """
        if self.switch_port_name not in SwitchPort.INSTANCES.keys():
            raise err_major(
                f"Switch port name {self.switch_port_name} in connection "
                f" {self.id} does not exist"
            )
        self._switch_port = SwitchPort.INSTANCES[self.switch_port_name]
        return self


class ECUPortToSwitchPort(ECUPortToXConnection):
    """
    Represents a connection from an ECU port to a switch port.

    Parameters
    ----------
    type : Literal["ecu_port_to_switch_port"]
        Type of the connection. Defaults to ``"ecu_port_to_switch_port"``.

    switch_port_name : str
        Name of the switch port (alias: ``switch_port``).

    Private Attributes
    ------------------
    _switch_port : :class:`~flync.model.flync_4_ecu.switch.SwitchPort`
        Internal reference to the actual SwitchPort object.
        Managed privately.
    """

    type: Literal["ecu_port_to_switch_port"] = Field("ecu_port_to_switch_port")

    switch_port_name: Annotated[str, Reference(source="_switch_port")] = Field(
        alias="switch_port"
    )

    _switch_port: Optional["SwitchPort"] = PrivateAttr(default=None)

    @property
    def switch_port(self) -> Optional["SwitchPort"]:
        return self._switch_port

    @model_validator(mode="after")
    def validate_connection_compatibility(self):
        """
        Check if the switch port referenced by the connection exists and
        validate optional MII configuration for compatibility.

        Raises:
        err_major: The specified switch port does not exist for
        this connection or  the optional MII configuration is invalid.

        """
        if self.switch_port_name not in SwitchPort.INSTANCES.keys():
            raise err_major(
                f"Switch port name {self.switch_port_name} in connection "
                f"{self.id} does not exist"
            )
        self._switch_port = SwitchPort.INSTANCES[self.switch_port_name]
        # Add connected component to each other
        self.ecu_port._connected_components.append(self.switch_port)
        self.switch_port._connected_component = self.ecu_port

        common_validators.validate_optional_mii_config_compatibility(
            self.ecu_port, self.switch_port, self.id
        )
        if self.ecu_port.mdi_config and self.switch_port.traffic_classes:
            common_validators.validate_cbs_idleslopes_fit_portspeed(
                self.switch_port.traffic_classes,
                self.ecu_port.mdi_config.speed,
            )
        # Once everything is validated, copy MDI config to Switch Port from
        # ECU Port.
        self.switch_port.copy_mdi_config_to_switch(self.ecu_port.mdi_config)
        return self


class ECUPortToControllerInterface(ECUPortToXConnection):
    """
    Represents a connection from an ECU port to a controller interface.

    Parameters
    ----------
    type : Literal["ecu_port_to_controller_interface"]
        Type of the connection.
        Defaults to ``"ecu_port_to_controller_interface"``.

    iface_name : str
        Name of the controller interface (alias: ``controller_interface``).

    Private Attributes
    ------------------
    _iface : :class:`~flync.model.flync_4_ecu.controller.ControllerInterface`
        Internal reference to the actual ControllerInterface object.
        Managed privately.
    """

    type: Literal["ecu_port_to_controller_interface"] = Field(
        "ecu_port_to_controller_interface"
    )

    _iface: Optional["ControllerInterface"] = PrivateAttr(default=None)
    iface_name: Annotated[str, Reference(source="_iface")] = Field(
        alias="controller_interface"
    )

    @property
    def iface(self) -> Optional["ControllerInterface"]:
        return self._iface

    @model_validator(mode="after")
    def validate_connection_compatibility(self):
        """
        Check if the controller interface referenced by the connection exists
        and validate optional MII, HTB configurations for compatibility.

        Raises:
            err_major: The specified controller interface does not exist for
            this connection or the MII,HTB configuration is invalid.
        """
        if self.iface_name not in ControllerInterface.INSTANCES.keys():
            raise err_major(
                f"Controller Interface name {self.iface_name} in connection"
                f"{self.id} does not exist"
            )
        self._iface = ControllerInterface.INSTANCES[self.iface_name]
        # Add connected component to each other
        self.ecu_port._connected_components.append(self.iface)
        self.iface._connected_component = self.ecu_port

        common_validators.validate_optional_mii_config_compatibility(
            self.ecu_port, self.iface, self.id
        )
        if self.iface.htb is not None:
            common_validators.validate_htb(
                self.iface, self.ecu_port.mdi_config.speed
            )
        return self


class SwitchPortToControllerInterface(SwitchPortToXConnection):
    """
    Represents a connection from a switch port to a controller interface.

    Parameters
    ----------
    type : Literal["switch_port_to_controller_interface"]
        Type of the connection.
        Defaults to ``"switch_port_to_controller_interface"``.

    iface_name : str
        Name of the controller interface (alias: ``controller_interface``).

    Private Attributes
    ------------------
    _iface : :class:`~flync.model.flync_4_ecu.controller.ControllerInterface`
        Internal reference to the actual ControllerInterface object.
        Managed privately.
    """

    type: Literal["switch_port_to_controller_interface"] = Field(
        "switch_port_to_controller_interface"
    )

    _iface: Optional["ControllerInterface"] = PrivateAttr(default=None)
    iface_name: Annotated[str, Reference(source="_iface")] = Field(
        alias="controller_interface"
    )

    @property
    def iface(self) -> Optional["ControllerInterface"]:
        return self._iface

    @model_validator(mode="after")
    def validate_connection_compatibility(self):
        """
        Check if the controller interface referenced by the
        connection exists andvalidate MII, HTB, MACsec and
        GPTP configurations for compatibility.

        Raises:
            err_major: The specified controller interface does not
            exist for this connection  or the MII,HTB
            MACSec or GPTP configuration is invalid.
        """
        if self.iface_name not in ControllerInterface.INSTANCES.keys():
            raise err_major(
                f"Controller Interface name {self.iface_name} in connection "
                f"{self.id} does not exist"
            )
        self._iface = ControllerInterface.INSTANCES[self.iface_name]
        # Add connected component to each other
        self.switch_port._connected_component = self.iface
        self.iface._connected_component = self.switch_port

        common_validators.validate_compulsory_mii_config_compatibility(
            self.switch_port, self.iface, self.id
        )
        if self.iface.htb is not None:
            common_validators.validate_htb(
                self.iface, self.iface.mii_config.speed
            )

        common_validators.validate_macsec(
            self.switch_port, self.iface, self.id
        )

        common_validators.validate_gptp(self.switch_port, self.iface, self.id)

        return self


class SwitchPortToSwitchPort(SwitchPortToXConnection):
    """
    Represents a connection between two switch ports on the same ECU.

    Parameters
    ----------
    type : Literal["switch_to_switch_same_ecu"]
        Type of the connection. Defaults to ``"switch_to_switch_same_ecu"``.

    switch2_port_name : str
        Name of the second switch port (alias: ``switch2_port``).

    Private Attributes
    ------------------
    _switch2_port : :class:`~flync.model.flync_4_ecu.switch.SwitchPort`
        Internal reference to the second switch port object.
        Managed privately.
    """

    type: Literal["switch_to_switch_same_ecu"] = Field(
        "switch_to_switch_same_ecu"
    )

    _switch2_port: Optional["SwitchPort"] = PrivateAttr(default=None)
    switch2_port_name: Annotated[str, Reference(source="_switch2_port")] = (
        Field(alias="switch2_port")
    )

    @property
    def switch2_port(self) -> Optional["SwitchPort"]:
        return self._switch2_port

    @model_validator(mode="after")
    def validate_connection_compatibility(self):
        """
        Check if the switch2 port referenced by the connection exists and
        validate MII, HTB, MACsec and GPTP configurations for compatibility.

        Raises:
            err_major: The specified controller interface does not exist for
            this connection or the MII,HTB
            MACSec or GPTP configuration is invalid.
        """
        if self.switch2_port_name not in SwitchPort.INSTANCES.keys():
            raise err_major(
                f"Switch port name {self.switch2_port_name} in connection "
                f"{self.id} does not exist"
            )
        self._switch2_port = SwitchPort.INSTANCES[self.switch2_port_name]

        # Add connected component to each other
        self.switch_port._connected_component = self.switch2_port
        self.switch2_port._connected_component = self.switch_port

        common_validators.validate_compulsory_mii_config_compatibility(
            self.switch_port, self.switch2_port, self.id
        )

        common_validators.validate_macsec(
            self.switch_port, self.switch2_port, self.id
        )
        common_validators.validate_gptp(
            self.switch_port, self.switch2_port, self.id
        )

        return self


class ControllerInterfaceToControllerInterface(InternalConnection):
    """
    Represents a direct connection between two controller interfaces in an ECU.

    Parameters
    ----------
    type : Literal["controller_interface_to_controller_interface"]
        Type of the connection. Defaults to \
        ``"controller_interface_to_controller_interface"``.

    iface_name : str
        Name of the first controller
        interface (alias: ``controller_interface1``).

    iface2_name : str
        Name of the second controller
        interface (alias: ``controller_interface2``).

    Private Attributes
    ------------------
    _iface : \
    :class:`~flync.model.flync_4_ecu.controller.ControllerInterface`
        Internal reference to the first controller interface.
        Managed privately.

    _iface2 : \
    :class:`~flync.model.flync_4_ecu.controller.ControllerInterface`
        Internal reference to the second controller interface.
        Managed privately.
    """

    type: Literal["controller_interface_to_controller_interface"] = Field(
        "controller_interface_to_controller_interface"
    )
    iface_name: Annotated[str, Reference(source="_iface")] = Field(
        alias="controller_interface1"
    )
    _iface: Optional["ControllerInterface"] = PrivateAttr(default=None)

    iface2_name: Annotated[str, Reference(source="_iface2")] = Field(
        alias="controller_interface2"
    )
    _iface2: Optional["ControllerInterface"] = PrivateAttr(default=None)

    @property
    def iface(self) -> Optional["ControllerInterface"]:
        return self._iface

    @property
    def iface2(self) -> Optional["ControllerInterface"]:
        return self._iface2

    @model_validator(mode="after")
    def validate_connection_compatibility(self):
        """
        Check if the controller interfaces referenced by the
        connection exists and validate compulsory MII, HTB,
        MACsec and GPTP configurations for compatibility.

        Raises:
            err_major: The specified controller interfaces does not
            exist for this connection or the MII,HTB
            MACSec or GPTP configuration is invalid.
        """
        if self.iface_name not in ControllerInterface.INSTANCES.keys():
            raise err_major(
                f"Controller Interface name {self.iface_name} in connection "
                f"{self.id} does not exist"
            )
        self._iface = ControllerInterface.INSTANCES[self.iface_name]

        if self.iface2_name not in ControllerInterface.INSTANCES.keys():
            raise err_major(
                f"Controller Interface name {self.iface2_name} in connection "
                f"{self.id} does not exist"
            )
        self._iface2 = ControllerInterface.INSTANCES[self.iface2_name]
        # Add connected component to each other
        self.iface._connected_component = self.iface2
        self.iface2._connected_component = self.iface
        common_validators.validate_compulsory_mii_config_compatibility(
            self.iface, self.iface2, self.id
        )
        if self.iface.htb is not None:
            common_validators.validate_htb(
                self.iface, self.iface.mii_config.speed
            )
        if self.iface2.htb is not None:
            common_validators.validate_htb(
                self.iface2, self.iface2.mii_config.speed
            )
        common_validators.validate_macsec(self.iface, self.iface2, self.id)
        common_validators.validate_gptp(self.iface, self.iface2, self.id)

        return self


class InternalConnectionUnion(RootModel):
    """
    Union type representing a connection between two internal
    ECU components.

    This model wraps a union of different internal connection
    types and uses the ``type`` field as a discriminator to
    determine which specific connection type is present.

    Possible types
    --------------
    :class:`~flync.model.flync_4_ecu.internal_topology.ECUPortToSwitchPort`
        Connection from an ECU port to a switch port.

    :class:`~flync.model.flync_4_ecu.internal_topology.ECUPortToControllerInterface`
        Connection from an ECU port to a controller interface.

    :class:`~flync.model.flync_4_ecu.internal_topology.SwitchPortToControllerInterface`
        Connection from a switch port to a controller interface.

    :class:`~flync.model.flync_4_ecu.internal_topology.SwitchPortToSwitchPort`
        Connection between two switch ports on the same ECU.

    :class:`~flync.model.flync_4_ecu.internal_topology.ControllerInterfaceToControllerInterface`
        Connection between two controller interfaces.
    """

    root: (
        ECUPortToSwitchPort
        | ECUPortToControllerInterface
        | SwitchPortToControllerInterface
        | SwitchPortToSwitchPort
        | ControllerInterfaceToControllerInterface
    ) = Field(discriminator="type")


class InternalTopology(FLYNCBaseModel):
    """
    Parameters
    ----------
    connections : list of :class:`InternalConnectionUnion`
        List of internal connections between ECU components.
        Defaults to an empty list.
    """

    connections: List[InternalConnectionUnion] = Field(default_factory=list)
