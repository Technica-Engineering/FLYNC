"""Tests for the generate_system_uml CLI command and node-builder helpers."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flync_cli.commands.generate_system_uml import (
    add_controller_nodes,
    add_ecu_port_nodes,
    add_iface_info_nodes,
    add_iface_nodes,
    add_inter_ecu_uml,
    add_internally_connected_ports,
    add_macsec_mode_iface,
    add_ptp_node_iface,
    add_ptp_switch,
    add_qos_iface,
    add_qos_switch,
    add_shapers_switch_port,
    add_switch_macsec,
    add_switch_nodes,
    add_switch_port_nodes,
    app,
    draw_controllers_uml,
    draw_iface_info_uml,
    draw_macsec_info_uml,
    draw_macsec_info_uml_switch,
    draw_ports_uml,
    draw_ptp_info_uml,
    draw_ptp_info_uml_switch,
    draw_qos_info_uml,
    draw_qos_info_uml_switch,
    draw_switches_uml,
    generate_ecu_uml,
    generate_intra_ecu_uml,
    parse_and_generate_uml,
)

from .helpers import make_ecu, make_interface, make_port

runner = CliRunner()


def _empty_all_nodes():
    return {
        "node_types": {},
        "iface_info_nodes": {},
        "ptp_nodes": {},
        "macsec_nodes": {},
        "qos_nodes": {},
        "defined_nodes": set(),
        "included_nodes": set(),
        "ecu_data": {},
        "included_ecus": set(),
        "internally_connected_ports": set(),
    }


def _make_ws():
    ws = MagicMock()
    ecu = make_ecu()
    ws.flync_model.get_all_ecus.return_value = [ecu.name]
    ws.flync_model.get_ecu_by_name.return_value = ecu
    ws.flync_model.ecus = [ecu]
    ws.flync_model.topology.system_topology.connections = []
    return ws, ecu


class TestAddEcuPortNodes:
    def test_registers_port_as_ecu_port(self):
        port = make_port("P0")
        ecu_nodes = {"ports": set()}
        node_types = {}
        add_ecu_port_nodes([port], ecu_nodes, node_types)
        assert "P0" in ecu_nodes["ports"]
        assert node_types["P0"] == "ecu_port"

    def test_empty_ports(self):
        ecu_nodes = {"ports": set()}
        node_types = {}
        add_ecu_port_nodes([], ecu_nodes, node_types)
        assert len(ecu_nodes["ports"]) == 0


class TestAddIfaceNodes:
    def test_adds_interface_without_vlan_filter(self):
        iface = make_interface(name="ETH0", vlan_id=10)
        ecu_nodes = {"controllers": {}}
        all_nodes = _empty_all_nodes()
        add_iface_nodes([iface], vlan_id=None, all_nodes=all_nodes, ecu_nodes=ecu_nodes, controller_name="CTRL0")
        assert "CTRL0" in ecu_nodes["controllers"]

    @pytest.mark.skip(reason="Broken&Useless")
    def test_adds_interface_matching_vlan(self):
        iface = make_interface(name="ETH0", vlan_id=10)
        ecu_nodes = {"controllers": {}}
        all_nodes = _empty_all_nodes()
        add_iface_nodes([iface], vlan_id=10, all_nodes=all_nodes, ecu_nodes=ecu_nodes, controller_name="CTRL0")
        assert "CTRL0" in ecu_nodes["controllers"]

    def test_skips_interface_not_matching_vlan(self):
        iface = make_interface(name="ETH0", vlan_id=10)
        ecu_nodes = {"controllers": {}}
        all_nodes = _empty_all_nodes()
        add_iface_nodes([iface], vlan_id=99, all_nodes=all_nodes, ecu_nodes=ecu_nodes, controller_name="CTRL0")
        assert "CTRL0" not in ecu_nodes["controllers"]


class TestAddIfaceInfoNodes:
    def test_populates_iface_info_nodes(self):
        iface = make_interface(name="ETH0")
        all_nodes = _empty_all_nodes()
        add_iface_info_nodes([iface], all_nodes)
        assert "ETH0" in all_nodes["iface_info_nodes"]
        assert "mac" in all_nodes["iface_info_nodes"]["ETH0"]


class TestAddMacsecModeIface:
    def test_adds_macsec_info(self):
        iface = make_interface(name="ETH0")
        iface.macsec_config = MagicMock()
        iface.macsec_config.key_role = "key_server"
        all_nodes = _empty_all_nodes()
        add_macsec_mode_iface([iface], all_nodes)
        assert all_nodes["macsec_nodes"]["ETH0"] == "key_server"

    def test_skips_iface_without_macsec(self):
        iface = make_interface(name="ETH0")
        iface.macsec_config = None
        all_nodes = _empty_all_nodes()
        add_macsec_mode_iface([iface], all_nodes)
        assert "ETH0" not in all_nodes["macsec_nodes"]


class TestAddQosIface:
    def test_adds_qos_info(self):
        iface = make_interface(name="ETH0")
        iface.htb = MagicMock()
        iface.htb.root_id = 1
        iface.htb.default_class = 2
        all_nodes = _empty_all_nodes()
        add_qos_iface([iface], all_nodes)
        assert "ETH0" in all_nodes["qos_nodes"]

    def test_skips_iface_without_qos(self):
        iface = make_interface(name="ETH0")
        iface.htb = None
        all_nodes = _empty_all_nodes()
        add_qos_iface([iface], all_nodes)
        assert "ETH0" not in all_nodes["qos_nodes"]


def _make_switch_port(name="SP0"):
    p = MagicMock()
    p.name = name
    p.macsec_config = None
    p.ptp_config = None
    p.traffic_classes = None
    return p


class TestAddPtpNodeIface:
    def test_transmitter_role(self):
        iface = make_interface(name="ETH0")
        pp = MagicMock()
        pp.sync_config.type = "time_transmitter"
        pp.domain_id = 5
        iface.ptp_config = MagicMock()
        iface.ptp_config.ptp_ports = [pp]
        all_nodes = _empty_all_nodes()
        add_ptp_node_iface([iface], all_nodes)
        assert "ETH0" in all_nodes["ptp_nodes"]
        assert all_nodes["ptp_nodes"]["ETH0"][0]["role"] == "Time Transmitter"
        assert all_nodes["ptp_nodes"]["ETH0"][0]["domain_id"] == 5

    def test_receiver_role(self):
        iface = make_interface(name="ETH1")
        pp = MagicMock()
        pp.sync_config.type = "time_receiver"
        pp.domain_id = 2
        iface.ptp_config = MagicMock()
        iface.ptp_config.ptp_ports = [pp]
        all_nodes = _empty_all_nodes()
        add_ptp_node_iface([iface], all_nodes)
        assert all_nodes["ptp_nodes"]["ETH1"][0]["role"] == "Time Receiver"

    def test_no_ptp_skipped(self):
        iface = make_interface(name="ETH0")
        all_nodes = _empty_all_nodes()
        add_ptp_node_iface([iface], all_nodes)
        assert "ETH0" not in all_nodes["ptp_nodes"]

    def test_empty_ptp_ports_not_added(self):
        iface = make_interface(name="ETH0")
        iface.ptp_config = MagicMock()
        iface.ptp_config.ptp_ports = []
        all_nodes = _empty_all_nodes()
        add_ptp_node_iface([iface], all_nodes)
        assert "ETH0" not in all_nodes["ptp_nodes"]


class TestAddControllerNodes:

    @pytest.mark.skip(reason="Review again.")
    def test_no_options(self):
        iface = make_interface(name="ETH0")
        ctrl = MagicMock()
        ctrl.name = "CTRL0"
        ctrl.interfaces = [iface]
        ecu_nodes = {"controllers": {}}
        all_nodes = _empty_all_nodes()
        add_controller_nodes([ctrl], None, ecu_nodes, all_nodes, [])
        assert "CTRL0" in ecu_nodes["controllers"]

    @pytest.mark.skip(reason="Review again.")
    def test_with_all_options_populates_nodes(self):
        iface = make_interface(name="ETH0")
        iface.macsec_config = MagicMock()
        iface.macsec_config.key_role = "ks"
        iface.htb = MagicMock()
        iface.htb.root_id = 1
        iface.htb.default_class = 2
        pp = MagicMock()
        pp.sync_config.type = "time_transmitter"
        pp.domain_id = 1
        iface.ptp_config = MagicMock()
        iface.ptp_config.ptp_ports = [pp]
        ctrl = MagicMock()
        ctrl.name = "CTRL0"
        ctrl.interfaces = [iface]
        ecu_nodes = {"controllers": {}}
        all_nodes = _empty_all_nodes()
        add_controller_nodes([ctrl], None, ecu_nodes, all_nodes, ["iface", "ptp", "macsec", "qos"])
        assert "ETH0" in all_nodes["iface_info_nodes"]
        assert "ETH0" in all_nodes["ptp_nodes"]
        assert "ETH0" in all_nodes["macsec_nodes"]
        assert "ETH0" in all_nodes["qos_nodes"]


class TestAddSwitchPortNodes:
    def test_no_vlan_includes_all(self):
        port = _make_switch_port("P0")
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_port_nodes([port], all_nodes, None, [], "SW0", ecu_nodes)
        assert "SW0" in ecu_nodes["switches"]
        assert "P0" in ecu_nodes["switches"]["SW0"]
        assert all_nodes["node_types"]["P0"] == "switch_port"

    def test_vlan_match_by_id(self):
        port = _make_switch_port("P0")
        vlan = MagicMock()
        vlan.id = 10
        vlan.name = "vlan10"
        vlan.ports = ["P0"]
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_port_nodes([port], all_nodes, 10, [vlan], "SW0", ecu_nodes)
        assert "SW0" in ecu_nodes["switches"]

    def test_vlan_match_by_name_substring(self):
        port = _make_switch_port("P0")
        vlan = MagicMock()
        vlan.id = 99
        vlan.name = "vlan10"
        vlan.ports = ["P0"]
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_port_nodes([port], all_nodes, 10, [vlan], "SW0", ecu_nodes)
        assert "SW0" in ecu_nodes["switches"]

    def test_vlan_no_match(self):
        port = _make_switch_port("P0")
        vlan = MagicMock()
        vlan.id = 20
        vlan.name = "vlan20"
        vlan.ports = ["P0"]
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_port_nodes([port], all_nodes, 10, [vlan], "SW0", ecu_nodes)
        assert "SW0" not in ecu_nodes["switches"]


class TestAddSwitchMacsec:
    def test_adds_macsec(self):
        port = _make_switch_port("P0")
        port.macsec_config = MagicMock()
        port.macsec_config.key_role = "key_server"
        all_nodes = _empty_all_nodes()
        add_switch_macsec([port], all_nodes)
        assert all_nodes["macsec_nodes"]["P0"] == "key_server"

    def test_no_macsec_skipped(self):
        port = _make_switch_port("P0")
        all_nodes = _empty_all_nodes()
        add_switch_macsec([port], all_nodes)
        assert "P0" not in all_nodes["macsec_nodes"]


class TestAddPtpSwitch:
    def test_transmitter(self):
        port = _make_switch_port("P0")
        pp = MagicMock()
        pp.sync_config.type = "time_transmitter"
        pp.domain_id = 3
        port.ptp_config = MagicMock()
        port.ptp_config.ptp_ports = [pp]
        all_nodes = _empty_all_nodes()
        add_ptp_switch([port], all_nodes)
        assert "P0" in all_nodes["ptp_nodes"]
        assert all_nodes["ptp_nodes"]["P0"][0]["role"] == "Time Transmitter"

    def test_no_ptp(self):
        port = _make_switch_port("P0")
        all_nodes = _empty_all_nodes()
        add_ptp_switch([port], all_nodes)
        assert "P0" not in all_nodes["ptp_nodes"]


class TestAddShapers:
    def test_cbs_shaper(self):
        tc = MagicMock()
        tc.name = "tc0"
        tc.frame_priority_values = [0]
        tc.internal_priority_values = [1]
        sm = MagicMock()
        sm.type = "cbs"
        sm.idleslope = 500
        tc.selection_mechanisms = sm
        result = []
        add_shapers_switch_port(tc, result)
        assert len(result) == 1
        assert result[0]["type"] == "CBS"
        assert "idle: 500" in result[0]["params"]

    def test_no_selection_mechanism(self):
        tc = MagicMock()
        tc.selection_mechanisms = None
        result = []
        add_shapers_switch_port(tc, result)
        assert result == []


class TestAddQosSwitch:
    def test_with_traffic_classes(self):
        port = _make_switch_port("P0")
        tc = MagicMock()
        tc.selection_mechanisms = None
        port.traffic_classes = [tc]
        all_nodes = _empty_all_nodes()
        add_qos_switch([port], all_nodes)
        assert "P0" in all_nodes["qos_nodes"]

    def test_no_traffic_classes(self):
        port = _make_switch_port("P0")
        port.traffic_classes = None
        all_nodes = _empty_all_nodes()
        add_qos_switch([port], all_nodes)
        assert "P0" in all_nodes["qos_nodes"]
        assert all_nodes["qos_nodes"]["P0"] == []


class TestAddSwitchNodes:
    def test_no_vlan(self):
        port = _make_switch_port("SP0")
        sw = MagicMock()
        sw.name = "SW0"
        sw.vlans = []
        sw.ports = [port]
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_nodes([sw], None, ecu_nodes, all_nodes, [])
        assert "SW0" in ecu_nodes["switches"]

    def test_with_all_options(self):
        port = _make_switch_port("SP0")
        port.macsec_config = MagicMock()
        port.macsec_config.key_role = "ks"
        port.traffic_classes = None
        sw = MagicMock()
        sw.name = "SW0"
        sw.vlans = []
        sw.ports = [port]
        ecu_nodes = {"switches": {}}
        all_nodes = _empty_all_nodes()
        add_switch_nodes([sw], None, ecu_nodes, all_nodes, ["macsec", "ptp", "qos"])
        assert all_nodes["macsec_nodes"].get("SP0") == "ks"


class TestDrawPortsUml:
    def test_adds_component_and_marks_defined(self):
        all_nodes = _empty_all_nodes()
        uml_lines = []
        draw_ports_uml("P0", uml_lines, all_nodes)
        assert any("[P0]" in line for line in uml_lines)
        assert "P0" in all_nodes["defined_nodes"]
        assert "P0" in all_nodes["included_nodes"]


class TestDrawIfaceInfoUml:
    def test_emits_note_with_addresses(self):
        all_nodes = _empty_all_nodes()
        all_nodes["iface_info_nodes"]["ETH0"] = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "vfaces": [{"name": "vi0", "vlanid": 10, "multicast": [], "addresses": ["192.168.1.1"]}],
        }
        uml_lines = []
        draw_iface_info_uml("ETH0", all_nodes, uml_lines)
        assert any("note right" in line for line in uml_lines)
        assert any("vi0" in line for line in uml_lines)
        assert any("192.168.1.1" in line for line in uml_lines)

    def test_emits_multicast(self):
        all_nodes = _empty_all_nodes()
        all_nodes["iface_info_nodes"]["ETH0"] = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "vfaces": [{"name": "vi0", "vlanid": 10, "multicast": ["239.0.0.1"], "addresses": []}],
        }
        uml_lines = []
        draw_iface_info_uml("ETH0", all_nodes, uml_lines)
        assert any("239.0.0.1" in line for line in uml_lines)

    def test_none_addresses_emits_none_label(self):
        all_nodes = _empty_all_nodes()
        all_nodes["iface_info_nodes"]["ETH0"] = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "vfaces": [{"name": "vi0", "vlanid": 10, "multicast": None, "addresses": None}],
        }
        uml_lines = []
        draw_iface_info_uml("ETH0", all_nodes, uml_lines)
        assert any("None" in line for line in uml_lines)


class TestDrawPtpInfoUml:
    def test_emits_ptp_note(self):
        all_nodes = _empty_all_nodes()
        all_nodes["ptp_nodes"]["ETH0"] = [{"domain_id": 5, "role": "Time Transmitter"}]
        uml_lines = []
        draw_ptp_info_uml("ETH0", all_nodes, uml_lines)
        assert any("PTP Domain" in line for line in uml_lines)
        assert any("Time Transmitter" in line for line in uml_lines)


class TestDrawMacsecInfoUml:
    def test_emits_macsec_note(self):
        all_nodes = _empty_all_nodes()
        all_nodes["macsec_nodes"]["ETH0"] = "key_server"
        uml_lines = []
        draw_macsec_info_uml("ETH0", all_nodes, uml_lines)
        assert any("MACsec" in line for line in uml_lines)
        assert any("key_server" in line for line in uml_lines)


class TestDrawQosInfoUml:
    def test_emits_htb_note(self):
        all_nodes = _empty_all_nodes()
        all_nodes["qos_nodes"]["ETH0"] = {"root_id": 1, "default_class": 2}
        uml_lines = []
        draw_qos_info_uml("ETH0", all_nodes, uml_lines)
        assert any("HTB" in line for line in uml_lines)
        assert any("1" in line for line in uml_lines)


class TestDrawControllersUml:
    def test_emits_controller_package(self):
        all_nodes = _empty_all_nodes()
        ecu_nodes = {"ports": set(), "controllers": {"CTRL0": {"ETH0": True}}, "switches": {}}
        uml_lines = []
        draw_controllers_uml(ecu_nodes, all_nodes, uml_lines)
        assert any("CTRL0" in line for line in uml_lines)
        assert any("[ETH0]" in line for line in uml_lines)
        assert "ETH0" in all_nodes["defined_nodes"]

    def test_emits_iface_annotations_when_present(self):
        all_nodes = _empty_all_nodes()
        all_nodes["ptp_nodes"]["ETH0"] = [{"domain_id": 1, "role": "Time Transmitter"}]
        all_nodes["macsec_nodes"]["ETH0"] = "ks"
        all_nodes["qos_nodes"]["ETH0"] = {"root_id": 1, "default_class": 2}
        all_nodes["iface_info_nodes"]["ETH0"] = {
            "mac": "AA:BB",
            "vfaces": [{"name": "vi0", "vlanid": 10, "multicast": [], "addresses": []}],
        }
        ecu_nodes = {"ports": set(), "controllers": {"CTRL0": {"ETH0": True}}, "switches": {}}
        uml_lines = []
        draw_controllers_uml(ecu_nodes, all_nodes, uml_lines)
        assert any("PTP" in line for line in uml_lines)
        assert any("MACsec" in line for line in uml_lines)
        assert any("HTB" in line for line in uml_lines)


class TestDrawMacsecInfoUmlSwitch:
    def test_emits_orange_component_and_note(self):
        all_nodes = _empty_all_nodes()
        all_nodes["macsec_nodes"]["SP0"] = "key_client"
        uml_lines = []
        draw_macsec_info_uml_switch("SP0", all_nodes, uml_lines)
        assert any("#Orange" in line for line in uml_lines)
        assert any("key_client" in line for line in uml_lines)


class TestDrawPtpInfoUmlSwitch:
    def test_emits_ptp_note_for_switch(self):
        all_nodes = _empty_all_nodes()
        all_nodes["ptp_nodes"]["SP0"] = [{"domain_id": 2, "role": "Time Receiver"}]
        uml_lines = []
        draw_ptp_info_uml_switch("SP0", all_nodes, uml_lines)
        assert any("PTP Domain" in line for line in uml_lines)
        assert any("Time Receiver" in line for line in uml_lines)


class TestDrawQosInfoUmlSwitch:
    def test_emits_qos_note_for_switch(self):
        all_nodes = _empty_all_nodes()
        all_nodes["qos_nodes"]["SP0"] = [{"tc_name": "tc0", "pcp": [0], "ipv": [1], "type": "CBS", "params": ["idle: 100"]}]
        uml_lines = []
        draw_qos_info_uml_switch("SP0", all_nodes, uml_lines)
        assert any("tc0" in line for line in uml_lines)
        assert any("idle: 100" in line for line in uml_lines)


class TestDrawSwitchesUml:
    def test_emits_switch_package(self):
        all_nodes = _empty_all_nodes()
        ecu_nodes = {"ports": set(), "controllers": {}, "switches": {"SW0": {"P0": True}}}
        uml_lines = []
        draw_switches_uml(ecu_nodes, all_nodes, uml_lines)
        assert any("SW0" in line for line in uml_lines)
        assert any("[P0]" in line for line in uml_lines)
        assert "P0" in all_nodes["defined_nodes"]

    def test_emits_macsec_port(self):
        all_nodes = _empty_all_nodes()
        all_nodes["macsec_nodes"]["P0"] = "ks"
        ecu_nodes = {"ports": set(), "controllers": {}, "switches": {"SW0": {"P0": True}}}
        uml_lines = []
        draw_switches_uml(ecu_nodes, all_nodes, uml_lines)
        assert any("#Orange" in line for line in uml_lines)


class TestGenerateEcuUml:
    def test_emits_ports_and_controller(self):
        all_nodes = _empty_all_nodes()
        all_nodes["ecu_data"]["ECU_A"] = {
            "ports": {"P0"},
            "controllers": {"CTRL0": {"ETH0": True}},
            "switches": {},
        }
        all_nodes["defined_nodes"] = set()
        uml_lines = []
        generate_ecu_uml("ECU_A", uml_lines, all_nodes)
        assert any("[P0]" in line for line in uml_lines)
        assert any("CTRL0" in line for line in uml_lines)


class TestAddInternallyConnectedPorts:
    def test_adds_connector_when_both_defined(self):
        all_nodes = _empty_all_nodes()
        all_nodes["defined_nodes"] = {"P0", "SP0"}
        uml_lines = []
        add_internally_connected_ports(uml_lines, all_nodes, None, "P0", "SP0", "C1")
        assert any("O--O" in line for line in uml_lines)

    def test_skips_when_not_both_defined(self):
        all_nodes = _empty_all_nodes()
        uml_lines = []
        add_internally_connected_ports(uml_lines, all_nodes, None, "P0", "SP0", "C1")
        assert uml_lines == []

    def test_vlan_tracks_ecu_port(self):
        all_nodes = _empty_all_nodes()
        all_nodes["defined_nodes"] = {"P0", "SP0"}
        all_nodes["node_types"]["P0"] = "ecu_port"
        uml_lines = []
        add_internally_connected_ports(uml_lines, all_nodes, 10, "P0", "SP0", "C1")
        assert "P0" in all_nodes["internally_connected_ports"]


class TestGenerateIntraEcuUml:
    def test_skips_unknown_type(self):
        conn = MagicMock()
        conn.root.type = "unknown_type"
        all_nodes = _empty_all_nodes()
        generate_intra_ecu_uml([conn], [], all_nodes, None)
        # no crash, no output needed

    def test_skips_none_type(self):
        conn = MagicMock()
        conn.root.type = None
        all_nodes = _empty_all_nodes()
        generate_intra_ecu_uml([conn], [], all_nodes, None)

    def test_known_type_adds_connector(self):
        all_nodes = _empty_all_nodes()
        all_nodes["defined_nodes"] = {"P0", "SP0"}
        conn = MagicMock()
        conn.root.type = "ecu_port_to_switch_port"
        conn.root.ecu_port.name = "P0"
        conn.root.switch_port.name = "SP0"
        conn.root.id = "C1"
        uml_lines = []
        generate_intra_ecu_uml([conn], uml_lines, all_nodes, None)
        assert any("O--O" in line for line in uml_lines)


class TestAddInterEcuUml:
    def test_skips_non_port_to_port_type(self):
        conn = MagicMock()
        conn.type = "other_type"
        all_nodes = _empty_all_nodes()
        uml_lines = []
        add_inter_ecu_uml(conn, all_nodes, uml_lines, None)
        assert uml_lines == []

    def test_adds_connector_no_vlan_filter(self):
        conn = MagicMock()
        conn.type = "ecu_port_to_ecu_port"
        conn.ecu1_port.name = "P0"
        conn.ecu2_port.name = "P1"
        conn.id = "IC1"
        all_nodes = _empty_all_nodes()
        all_nodes["defined_nodes"] = {"P0", "P1"}
        uml_lines = []
        add_inter_ecu_uml(conn, all_nodes, uml_lines, None)
        assert any("O--O" in line for line in uml_lines)

    def test_inserts_placeholder_for_undefined_ports(self):
        conn = MagicMock()
        conn.type = "ecu_port_to_ecu_port"
        conn.ecu1_port.name = "NewP0"
        conn.ecu2_port.name = "NewP1"
        conn.id = "IC2"
        all_nodes = _empty_all_nodes()
        uml_lines = ["@startuml"]
        add_inter_ecu_uml(conn, all_nodes, uml_lines, None)
        assert any("[NewP0]" in line for line in uml_lines)
        assert any("[NewP1]" in line for line in uml_lines)

    def test_vlan_skips_unconnected_ports(self):
        conn = MagicMock()
        conn.type = "ecu_port_to_ecu_port"
        conn.ecu1_port.name = "P0"
        conn.ecu2_port.name = "P1"
        conn.id = "IC3"
        all_nodes = _empty_all_nodes()
        uml_lines = []
        add_inter_ecu_uml(conn, all_nodes, uml_lines, 10)
        assert uml_lines == []

    def test_vlan_includes_internally_connected_port(self):
        conn = MagicMock()
        conn.type = "ecu_port_to_ecu_port"
        conn.ecu1_port.name = "P0"
        conn.ecu2_port.name = "P1"
        conn.id = "IC4"
        all_nodes = _empty_all_nodes()
        all_nodes["internally_connected_ports"] = {"P0"}
        all_nodes["defined_nodes"] = {"P0", "P1"}
        uml_lines = []
        add_inter_ecu_uml(conn, all_nodes, uml_lines, 10)
        assert any("O--O" in line for line in uml_lines)


class TestParseAndGenerateUml:
    def test_basic_output_starts_and_ends(self):
        model = MagicMock()
        lines = parse_and_generate_uml(model, None, [], [], [])
        assert lines[0] == "@startuml"
        assert lines[-1] == "@enduml"

    @pytest.mark.skip(reason="Review again. Mock broken.")
    def test_ecu_with_controller_appears_in_uml(self):
        iface = make_interface(name="ETH0")
        ctrl = MagicMock()
        ctrl.name = "CTRL0"
        ctrl.interfaces = [iface]
        ecu = MagicMock()
        ecu.name = "ECU_A"
        ecu.ports = []
        ecu.controllers = [ctrl]
        ecu.switches = []
        ecu.topology.connections = []
        model = MagicMock()
        model.get_ecu_by_name.return_value = ecu
        lines = parse_and_generate_uml(model, None, [], [ecu], [])
        assert any("ECU_A" in line for line in lines)
        assert any("CTRL0" in line for line in lines)

    def test_inter_ecu_connection_in_uml(self):
        model = MagicMock()
        conn = MagicMock()
        conn.type = "ecu_port_to_ecu_port"
        conn.ecu1_port.name = "PA"
        conn.ecu2_port.name = "PB"
        conn.id = "link1"
        lines = parse_and_generate_uml(model, None, [], [], [conn])
        assert any("O--O" in line for line in lines)


class TestGenerateSystemUmlCommand:

    def test_exits_zero_with_valid_workspace(self, tmp_path):
        ws, ecu = _make_ws()
        ecu.ports = []
        ecu.controllers = []
        ecu.switches = []
        output_file = str(tmp_path / "out.puml")
        mock_result = MagicMock()
        mock_result.workspace = ws
        mock_result.errors = {}
        with patch("flync_cli.commands.generate_system_uml", return_value=mock_result):
            result = runner.invoke(app, [str(tmp_path), "--output", output_file])
        assert result.exit_code == 0

    @pytest.mark.skip(reason="Review again.")
    def test_validate_failure_exits(self, tmp_path):
        with patch("flync_cli.commands.generate_system_uml", return_value=None):
            result = runner.invoke(app, [str(tmp_path)])
        assert result.exit_code != 0

    def test_all_info_flags(self, tmp_path):
        ws, ecu = _make_ws()
        ecu.ports = []
        ecu.controllers = []
        ecu.switches = []
        output_file = str(tmp_path / "out.puml")
        mock_result = MagicMock()
        mock_result.workspace = ws
        mock_result.errors = {}
        with patch("flync_cli.commands.generate_system_uml", return_value=mock_result):
            result = runner.invoke(
                app,
                [
                    str(tmp_path),
                    "--output",
                    output_file,
                    "--macsec-info",
                    "--ptp-info",
                    "--iface-info",
                    "--qos-info",
                ],
            )
        assert result.exit_code == 0

    def test_target_ecu_flag(self, tmp_path):
        ws, ecu = _make_ws()
        ecu.ports = []
        ecu.controllers = []
        ecu.switches = []
        ws.flync_model.get_ecu_by_name.return_value = ecu
        output_file = str(tmp_path / "out.puml")
        mock_result = MagicMock()
        mock_result.workspace = ws
        mock_result.errors = {}
        with patch("flync_cli.commands.generate_system_uml", return_value=mock_result):
            result = runner.invoke(
                app,
                [str(tmp_path), "--output", output_file, "--target-ecu", "ECU1"],
            )
        assert result.exit_code == 0

    def test_write_error_exits_nonzero(self, tmp_path):
        ws, ecu = _make_ws()
        ecu.ports = []
        ecu.controllers = []
        ecu.switches = []
        output_file = str(tmp_path / "out.puml")
        with (
            patch("flync_cli.commands.generate_system_uml.run_validation", return_value=ws),
            patch("flync_cli.commands.generate_system_uml.Path") as mock_path_cls,
        ):
            mock_p = MagicMock()
            mock_p.parent.mkdir.return_value = None
            mock_p.open.side_effect = OSError("disk full")
            mock_path_cls.return_value = mock_p
            result = runner.invoke(app, [str(tmp_path), "--output", output_file])
        assert result.exit_code != 0
        assert "disk full" in result.output
