"""Factory helpers for building mock FLYNC model objects in CLI tests."""

from unittest.mock import MagicMock


def make_virtual_iface(vlanid=10, name="vi0", ips=None, multicast=None):
    vi = MagicMock()
    vi.vlanid = vlanid
    vi.name = name
    vi.multicast = multicast or []
    vi.addresses = []
    for ip in ips or []:
        addr = MagicMock()
        addr.address = ip
        vi.addresses.append(addr)
    return vi


def make_interface(name="ETH0", vlan_id=10, ips=None):
    iface = MagicMock()
    iface.name = name
    iface.virtual_interfaces = [make_virtual_iface(vlanid=vlan_id, ips=ips or ["192.168.1.1"])]
    iface.mac_address = "AA:BB:CC:DD:EE:FF"
    iface.ptp_config = None
    iface.macsec_config = None
    iface.htb = None
    return iface


def make_controller(name="ETH_CTRL", iface_name="ETH0"):
    ctrl = MagicMock()
    ctrl.name = name
    ctrl.interfaces = [make_interface(name=iface_name)]
    ctrl.get_all_ips.return_value = ["192.168.1.1"]
    return ctrl


def make_switch(name="SW0"):
    sw = MagicMock()
    sw.name = name
    sw.vlans = []
    sw.ports = []
    sw.host_controller = None
    return sw


def make_port(name="PORT0"):
    port = MagicMock()
    port.name = name
    return port


def make_ecu(name="ECU1"):
    ecu = MagicMock()
    ecu.name = name
    ecu.get_all_controllers.return_value = [make_controller()]
    ecu.get_all_switches.return_value = [make_switch()]
    ecu.get_all_ports.return_value = [make_port()]
    ecu.get_all_interfaces.return_value = [make_interface()]
    ecu.get_all_ips.return_value = ["192.168.1.1"]
    ecu.sockets = []
    ecu.topology = MagicMock()
    ecu.topology.connections = []
    return ecu
