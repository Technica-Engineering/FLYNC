import pytest
from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.model.flync_4_ecu.controller import (
    VirtualControllerInterface,
    Controller,
    ControllerInterface,
)

from flync.model.flync_4_someip.service_interface import (
    SDTimings,
)
from flync.model.flync_4_ecu.switch import (
    MulticastGroup,
    SwitchPort,
    VLANEntry,
)
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.phy import MII, BASET1
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
    SocketTCP,
    SocketUDP,
    TCPOption,
    UDPOption,
)
from flync.model.flync_4_tsn.qos import (
    CBSShaper,
    ATSShaper,
    ATSInstance,
    SingleRateTwoColorMarker,
    SingleRateThreeColorMarker,
    DoubleRateThreeColorMarker,
)
from flync.model.flync_4_ecu.phy import MII
from flync.model.flync_4_security.macsec import (
    IntegrityWithConfidentiality,
    IntegrityWithoutConfidentiality,
)


@pytest.fixture
def metadata_entry():
    metadata_entry = dict(
        {
            "author": "Dev",
            "compatible_flync_version": {
                "version_schema": "semver",
                "version": "0.9.0",
            },
        }
    )
    yield metadata_entry


@pytest.fixture
def embedded_metadata_entry():
    embedded_metadata_entry = dict(
        {
            "author": "Dev",
            "compatible_flync_version": {
                "version_schema": "semver",
                "version": "0.9.0",
            },
            "target_system": "every",
        }
    )
    yield embedded_metadata_entry


@pytest.fixture
def ipv4_entry():
    ipv4_entry = IPv4AddressEntry(
        address="10.0.0.1", ipv4netmask="255.255.255.0"
    )
    yield ipv4_entry


@pytest.fixture
def ipv4_addressendpoint():
    ipv4_address_endpoint = IPv4AddressEndpoint(
        address="10.0.0.1", ipv4netmask="255.255.255.0"
    )
    yield ipv4_address_endpoint


@pytest.fixture
def ipv6_address_endpoint():

    ipv6_address_endpoint = IPv6AddressEndpoint(
        address="2001:0db8:85a3:0000:0000:8a2e:0370:7334", ipv6prefix=128
    )
    yield ipv6_address_endpoint


@pytest.fixture
def CBSShaper_entry():
    CBSShaper_entry = CBSShaper(type="cbs", idleslope=200000)
    yield CBSShaper_entry


@pytest.fixture
def ATSShaper_entry():
    ATSShaper_entry = ATSShaper(type="ats")
    yield ATSShaper_entry


@pytest.fixture
def SingleRateTwoColorMarker_entry():
    SingleRateTwoColorMarker_entry = SingleRateTwoColorMarker(
        type="single_rate_two_color",
        cir=1000,
        cbs=1000,
        ebs=1000,
        eir=0,
        coupling=False,
    )
    yield SingleRateTwoColorMarker_entry


@pytest.fixture
def SingleRateThreeColorMarker_entry():
    SingleRateThreeColorMarker_entry = SingleRateThreeColorMarker(
        type="single_rate_three_color",
        cir=1000,
        cbs=1000,
        ebs=1000,
        eir=0,
        coupling=True,
    )
    yield SingleRateThreeColorMarker_entry


@pytest.fixture
def DoubleRateThreeColorMarker_entry():
    DoubleRateThreeColorMarker_entry = DoubleRateThreeColorMarker(
        type="double_rate_three_color",
        cir=1000,
        cbs=1000,
        ebs=2000,
        eir=1000,
        coupling=False,
    )
    yield DoubleRateThreeColorMarker_entry


@pytest.fixture
def ATSInstance_entry():
    ATSShaper_entry = ATSInstance(
        committed_information_rate=100,
        committed_burst_size=100,
        max_residence_time=1,
    )
    yield ATSShaper_entry


@pytest.fixture
def integrity_without_confidentiality_entry():
    integrity_without_confidentiality_entry = IntegrityWithoutConfidentiality(
        type="integrity_without_confidentiality", offset_preference=0
    )
    yield integrity_without_confidentiality_entry


@pytest.fixture
def integrity_with_confidentiality_entry():
    integrity_with_confidentiality_entry = IntegrityWithConfidentiality(
        type="integrity_with_confidentiality", offset_preference=0
    )
    yield integrity_with_confidentiality_entry


@pytest.fixture
def MII_entry():
    MII_entry = MII(type="mii", speed=100, mode="mac")
    yield MII_entry


@pytest.fixture
def ipv6_entry():
    ipv6_entry = IPv6AddressEntry(
        address="2001:0db8:85a3:0000:0000:8a2e:0370:7334", ipv6prefix=128
    )
    yield ipv6_entry


@pytest.fixture
def vlan_entry():
    vlan_entry = VLANEntry(
        name="vlan_test",
        id=10,
        default_priority=1,
        ports=["port1"],
        multicast=None,
    )
    yield vlan_entry


@pytest.fixture
def mcastv4_group():
    multicast_group = MulticastGroup(
        address="224.0.0.1", ports=["port1, port2"]
    )
    yield multicast_group


@pytest.fixture
def mcastv6_group():
    multicast_group = MulticastGroup(address="FF02::1", ports=["port1, port2"])
    yield multicast_group


@pytest.fixture
def ecu_port():
    ecu_port = ECUPort(
        name="valid_ecu_port",
        mdi_config=BASET1(speed=100, role="slave"),
        mii_config=MII(mode="phy"),
    )
    yield ecu_port


@pytest.fixture
def virtual_controller_interface(ipv4_addressendpoint, ipv6_address_endpoint):
    virtual_controller_interface = VirtualControllerInterface(
        name="valid_virtual_ctrl_iface",
        vlanid=20,
        addresses=[ipv4_addressendpoint, ipv6_address_endpoint],
        multicast=["224.0.0.1", "224.0.0.2", "224.0.0.2"],
    )
    yield virtual_controller_interface


@pytest.fixture
def switch_port():
    switch_port = SwitchPort(
        name="valid_switch_port", default_vlan_id=1, silicon_port_no=1
    )
    yield switch_port


@pytest.fixture
def switch_host_controller_example(virtual_controller_interface):
    host_ctrl = {
        "name": "iface1",
        "mac_address": "10:10:10:22:22:22",
        "virtual_interfaces": [virtual_controller_interface],
    }

    yield host_ctrl


@pytest.fixture
def controller(virtual_controller_interface):
    ctrl = Controller(
        name="valid_controller",
        interfaces=[
            ControllerInterface(
                name="ci",
                mac_address="de:ad:be:ef:69:69",
                mii_config=MII(mode="mac"),
                virtual_interfaces=[],
            )
        ],
    )
    yield ctrl


@pytest.fixture
def tcp_socket_entry_ipv4():
    tcp_options = TCPOption(tcp_profile_id=1)
    tcp_socket_entry_ipv4 = SocketTCP(
        endpoint_address="10.0.1.1",
        name="my_socket",
        port_no=4400,
        tcp_profile=1,
        protocol="tcp",
    )
    yield tcp_socket_entry_ipv4


@pytest.fixture
def udp_socket_entry_ipv4():
    udp_socket_entry_ipv4 = SocketUDP(
        endpoint_address="10.0.1.1",
        name="my_socket",
        port_no=4400,
        udp_options=UDPOption(),
        protocol="udp",
    )
    yield udp_socket_entry_ipv4


@pytest.fixture
def tcp_socket_entry_ipv6():
    tcp_options = TCPOption(tcp_profile_id=1)
    tcp_socket_entry_ipv6 = SocketTCP(
        endpoint_address="2001:db8:85a3::8a2e:370:7334",
        name="my_socket",
        port_no=4400,
        tcp_profile=1,
        protocol="tcp",
    )
    yield tcp_socket_entry_ipv6


@pytest.fixture
def udp_socket_entry_ipv6():
    udp_socket_entry_ipv6 = SocketUDP(
        endpoint_address="2001:db8:85a3::8a2e:370:7334",
        name="my_socket",
        port_no=4400,
        udp_options=UDPOption(),
        protocol="udp",
    )
    yield udp_socket_entry_ipv6


# @pytest.fixture
# def someip_timings_profile_entry():
#     someip_timings_profile_entry = SOMEIPTimings(
#         time_domain=1, sd_timings=SDTimings()
#     )
#     yield someip_timings_profile_entry


@pytest.fixture
def someip_sd_server_timings_profile_entry():
    someip_sd_timings_profile_entry = SDTimings(
        profile_id="server_default",
        initial_delay_min=0.050,
        initial_delay_max=0.100,
        repetitions_base_delay=0.300,
        repetitions_max=3,
        request_response_delay_min=0.050,
        request_response_delay_max=0.100,
        offer_cyclic_delay=1,
        offer_ttl=3,
    )
    yield someip_sd_timings_profile_entry


@pytest.fixture
def someip_sd_client_timings_profile_entry():
    someip_sd_timings_profile_entry = SDTimings(
        profile_id="client_default",
        initial_delay_min=0.050,
        initial_delay_max=0.100,
        repetitions_base_delay=0.300,
        repetitions_max=3,
        request_response_delay_min=0.050,
        request_response_delay_max=0.100,
        find_ttl=3,
        subscribe_ttl=3,
    )
    yield someip_sd_timings_profile_entry
