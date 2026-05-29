from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from flync_cli.utils.mapping import get_mapping
from flync_cli.utils.run_validation import run_validation

console = Console(force_terminal=True)
app = typer.Typer()

END_NOTE = "    end note"


def add_ecu_port_nodes(ports, ecu_nodes, node_types):
    """Register ECU ports as nodes in the UML diagram."""
    for port in ports:
        port_name = port.name
        ecu_nodes["ports"].add(port_name)
        node_types[port_name] = "ecu_port"


def add_iface_nodes(interfaces, vlan_id, all_nodes, ecu_nodes, controller_name):
    """Add controller interface nodes, optionally filtered by VLAN ID."""
    iface_dict = {}
    include_controller = False
    for tmp in interfaces:
        iface = tmp.interface_config
        iface_name = iface.name
        include_iface = True
        if vlan_id is not None:
            virtual_ifaces = iface.virtual_interfaces
            include_iface = any(vif.vlanid == vlan_id for vif in virtual_ifaces)
        if include_iface:
            iface_dict[iface_name] = True
            all_nodes["node_types"][iface_name] = "controller_interface"
            include_controller = True
    if include_controller:
        ecu_nodes["controllers"][controller_name] = iface_dict


def add_iface_info_nodes(interfaces, all_nodes):
    """Collect interface metadata (MAC, VLANs, multicast, IPs) for diagram annotations."""
    for iface in interfaces:
        iface_name = iface.name
        viface_list = []

        vifaces = iface.virtual_interfaces
        mac_address = iface.mac_address

        for viface in vifaces:
            viface_info = {
                "name": viface.name,
                "vlanid": viface.vlanid,
                "multicast": viface.multicast,
                "addresses": [addr.address for addr in viface.addresses],
            }
            viface_list.append(viface_info)

        all_nodes["iface_info_nodes"][iface_name] = {
            "mac": mac_address,
            "vfaces": viface_list,
        }


def add_ptp_node_iface(interfaces, all_nodes):
    """Collect PTP configuration from interfaces for diagram annotations."""
    for iface in interfaces:
        iface_name = iface.name
        ptp_port_list = []
        if iface.ptp_config:
            for ptp_port in iface.ptp_config.ptp_ports:
                if ptp_port.sync_config.type == "time_transmitter":
                    role = "Time Transmitter"
                else:
                    role = "Time Receiver"
                ptp_info = {
                    "domain_id": ptp_port.domain_id,
                    "role": role,
                }
                ptp_port_list.append(ptp_info)
            if ptp_port_list != []:
                all_nodes["ptp_nodes"][iface_name] = ptp_port_list


def add_macsec_mode_iface(interfaces, all_nodes):
    """Collect MACsec configuration from interfaces for diagram annotations."""
    for iface in interfaces:
        iface_name = iface.name
        if iface.macsec_config:
            macsec_config = iface.macsec_config
            key_role = macsec_config.key_role
            all_nodes["macsec_nodes"][iface_name] = key_role


def add_qos_iface(interfaces, all_nodes):
    """Collect QoS (HTB) configuration from interfaces for diagram annotations."""
    for iface in interfaces:
        iface_name = iface.name
        if iface.htb:
            htb_config = iface.htb
            root_id = htb_config.root_id
            default_class = htb_config.default_class
            htb_info = {
                "root_id": root_id,
                "default_class": default_class,
            }
            all_nodes["qos_nodes"][iface_name] = htb_info


def add_controller_nodes(controllers, vlan_id, ecu_nodes, all_nodes, options):
    """Process controllers and collect interfaces with optional feature info (iface, ptp, macsec, qos)."""
    for controller in controllers:
        controller_name = controller.name
        interfaces = controller.ethernet_interfaces
        add_iface_nodes(
            interfaces,
            vlan_id,
            all_nodes,
            ecu_nodes,
            controller_name,
        )

        if "iface" in options:
            add_iface_info_nodes(interfaces, all_nodes)
        if "ptp" in options:
            add_ptp_node_iface(interfaces, all_nodes)
        if "macsec" in options:
            add_macsec_mode_iface(interfaces, all_nodes)
        if "qos" in options:
            add_qos_iface(interfaces, all_nodes)


def add_switch_port_nodes(ports, all_nodes, vlan_id, vlans, switch_name, ecu_nodes):
    """Register switch ports as nodes, optionally filtered by VLAN ID."""
    match_vlan = False
    allowed_ports = set()
    if vlan_id is not None:
        for vlan in vlans:
            if vlan.id == vlan_id or str(vlan_id) in vlan.name:
                match_vlan = True
                allowed_ports = set(vlan.ports)
                break
    else:
        match_vlan = True
        allowed_ports = set(p.name for p in ports)

    if match_vlan:
        port_dict = {}
        for port in ports:
            port_name = port.name
            if port_name in allowed_ports:
                port_dict[port_name] = True
                all_nodes["node_types"][port_name] = "switch_port"
        ecu_nodes["switches"][switch_name] = port_dict


def add_switch_macsec(ports, all_nodes):
    """Collect MACsec configuration from switch ports for diagram annotations."""
    for port in ports:
        port_name = port.name
        if port.macsec_config:
            macsec_config = port.macsec_config
            key_role = macsec_config.key_role
            all_nodes["macsec_nodes"][port_name] = key_role


def add_ptp_switch(ports, all_nodes):
    """Collect PTP configuration from switch ports for diagram annotations."""
    for port in ports:
        port_name = port.name
        ptp_port_list = []
        if port.ptp_config:
            for ptp_port in port.ptp_config.ptp_ports:
                if ptp_port.sync_config.type == "time_transmitter":
                    role = "Time Transmitter"
                else:
                    role = "Time Receiver"
                ptp_info = {
                    "domain_id": ptp_port.domain_id,
                    "role": role,
                }
                ptp_port_list.append(ptp_info)
        if ptp_port_list != []:
            all_nodes["ptp_nodes"][port_name] = ptp_port_list


def add_shapers_switch_port(tc, port_shaper_list):
    """Extract and format traffic class shaper information (CBS/ATS) for a switch port."""
    sm = tc.selection_mechanisms
    if sm:
        shaper_info = {
            "tc_name": tc.name,
            "pcp": tc.frame_priority_values,
            "ipv": tc.internal_priority_values,
        }

        if sm.type == "cbs":
            shaper_info["type"] = "CBS"
            shaper_info["params"] = ["idle: " + str(sm.idleslope)]

        elif sm.get("type") == "ats":
            shaper_info["type"] = "ATS"

        port_shaper_list.append(shaper_info)


def add_qos_switch(ports, all_nodes):
    """Collect QoS traffic class configuration from switch ports for diagram annotations."""
    for port in ports:
        port_shaper_list = []
        port_name = port.name
        traffic_classes = port.traffic_classes
        if traffic_classes is not None:
            for tc in traffic_classes:
                add_shapers_switch_port(tc, port_shaper_list)
        all_nodes["qos_nodes"][port_name] = port_shaper_list


def add_switch_nodes(switches, vlan_id, ecu_nodes, all_nodes, options):
    """Process switches and collect ports with optional feature info (macsec, ptp, qos)."""
    for switch in switches:
        switch_name = switch.name
        vlans = switch.vlans
        ports = switch.ports
        add_switch_port_nodes(
            ports,
            all_nodes,
            vlan_id,
            vlans,
            switch_name,
            ecu_nodes,
        )

        if "macsec" in options:
            add_switch_macsec(ports, all_nodes)

        if "ptp" in options:
            add_ptp_switch(ports, all_nodes)

        if "qos" in options:
            add_qos_switch(ports, all_nodes)


def draw_ports_uml(port_name, uml_lines, all_nodes):
    """Add a port node to UML output."""
    uml_lines.append(f"  [{port_name}] #PaleGreen")
    all_nodes["defined_nodes"].add(port_name)
    all_nodes["included_nodes"].add(port_name)


def draw_iface_info_uml(iface_name, all_nodes, uml_lines):
    """Draw interface metadata annotations (MAC, VLANs, multicast, IPs) in UML."""
    for viface in all_nodes["iface_info_nodes"][iface_name]["vfaces"]:
        uml_lines.append(f"    note right of [{iface_name}] #RosyBrown")
        uml_lines.append(f'        **viface: {viface.get("name")}**')
        uml_lines.append(f"        vlan_id: " f'{viface.get("vlanid")}')
        if not viface.get("multicast"):

            uml_lines.append("        multicast: None")
        else:
            uml_lines.append("        multicast:")
            for add in viface.get("multicast"):
                uml_lines.append(f"        - {add}")
        if not viface.get("addresses"):

            uml_lines.append("        ip_addresses: None")
        else:
            uml_lines.append("        ip_addresses:")
            for add in viface.get("addresses"):
                uml_lines.append(f"        - {add}")
        uml_lines.append(END_NOTE)


def draw_ptp_info_uml(iface_name, all_nodes, uml_lines):
    """Draw PTP configuration annotations in UML."""
    for ptp_port in all_nodes["ptp_nodes"][iface_name]:
        uml_lines.append(f"    note right of [{iface_name}] #HotPink")
        uml_lines.append("        **PTP Domain: " f'{ptp_port.get("domain_id")}**')
        uml_lines.append(f'        PTP Role: {ptp_port.get("role")}')
        uml_lines.append(END_NOTE)


def draw_macsec_info_uml(iface_name, all_nodes, uml_lines):
    """Draw MACsec configuration annotations in UML."""
    uml_lines.append(f"    note right of [{iface_name}] #MediumOrchid")
    uml_lines.append("        **MACsec**")
    uml_lines.append(f"        {all_nodes["macsec_nodes"][iface_name]}")
    uml_lines.append(END_NOTE)


def draw_qos_info_uml(iface_name, all_nodes, uml_lines):
    """Draw QoS (HTB) configuration annotations in UML."""
    uml_lines.append(f"    note right of [{iface_name}] #Gold")
    uml_lines.append("        **HTB**")
    uml_lines.append(f'        Root ID: {all_nodes["qos_nodes"][iface_name]["root_id"]}')
    uml_lines.append("        Default Class: " f'{all_nodes["qos_nodes"][iface_name]["default_class"]}')
    uml_lines.append(END_NOTE)


def draw_controllers_uml(ecu_nodes, all_nodes, uml_lines):
    """Draw all controllers and their interfaces with optional annotations in UML."""
    uml_lines.append("  ' Controllers")
    for controller_name, iface_dict in ecu_nodes["controllers"].items():
        uml_lines.append(f'  package "Controller: {controller_name}" ' f"#LightSteelBlue {{")
        for iface_name in iface_dict:

            uml_lines.append(f"    [{iface_name}] #SteelBlue")

            if iface_name in all_nodes["iface_info_nodes"]:
                draw_iface_info_uml(iface_name, all_nodes, uml_lines)

            if iface_name in all_nodes["ptp_nodes"]:
                draw_ptp_info_uml(iface_name, all_nodes, uml_lines)

            if iface_name in all_nodes["macsec_nodes"].keys():
                draw_macsec_info_uml(iface_name, all_nodes, uml_lines)

            if iface_name in all_nodes["qos_nodes"]:
                draw_qos_info_uml(iface_name, all_nodes, uml_lines)

            all_nodes["defined_nodes"].add(iface_name)
            all_nodes["included_nodes"].add(iface_name)

        uml_lines.append("  }")


def draw_macsec_info_uml_switch(port_name, all_nodes, uml_lines):
    """Draw MACsec configuration annotation for a switch port in UML."""
    uml_lines.append(f"    [{port_name}] #Orange")
    uml_lines.append(f"    note right of [{port_name}] #MediumOrchid")
    uml_lines.append("        **MACsec**")
    uml_lines.append(f"        {all_nodes["macsec_nodes"][port_name]}")
    uml_lines.append(END_NOTE)


def draw_ptp_info_uml_switch(port_name, all_nodes, uml_lines):
    """Draw PTP configuration annotations for a switch port in UML."""
    for ptp_port in all_nodes["ptp_nodes"][port_name]:
        uml_lines.append(f"    note right of [{port_name}] #HotPink")
        uml_lines.append(f"        **PTP Domain: " f'{ptp_port.get("domain_id")}**')
        uml_lines.append(f'        PTP Role: {ptp_port.get("role")}')
        uml_lines.append(END_NOTE)


def draw_qos_info_uml_switch(port_name, all_nodes, uml_lines):
    """Draw QoS traffic class annotations for a switch port in UML."""
    for tc in all_nodes["qos_nodes"][port_name]:
        uml_lines.append(f"    note right of [{port_name}] #Gold")
        uml_lines.append(f'        **{tc["tc_name"]}**')
        uml_lines.append(f'        pcp: {tc["pcp"]}')
        uml_lines.append(f'        ipv: {tc["ipv"]}')
        uml_lines.append(f'        **{tc.get("type", "None")}**')

        params = tc.get("params", [])
        for param in params:
            uml_lines.append(f"        {param}")

        uml_lines.append(END_NOTE)


def draw_switches_uml(ecu_nodes, all_nodes, uml_lines):
    """Draw all switches and their ports with optional annotations in UML."""
    uml_lines.append("  ' Switches")
    for switch_name, port_dict in ecu_nodes["switches"].items():
        uml_lines.append(f'  package "Switch: {switch_name}" ' f"#LightGoldenRodYellow{{")
        for port_name in port_dict:

            if port_name in all_nodes["macsec_nodes"].keys():
                draw_macsec_info_uml_switch(port_name, all_nodes, uml_lines)
            else:
                uml_lines.append(f"    [{port_name}] #LightSalmon")

            if port_name in all_nodes["ptp_nodes"]:
                draw_ptp_info_uml_switch(port_name, all_nodes, uml_lines)

            if port_name in all_nodes["qos_nodes"]:
                draw_qos_info_uml_switch(port_name, all_nodes, uml_lines)

            all_nodes["defined_nodes"].add(port_name)
            all_nodes["included_nodes"].add(port_name)
        uml_lines.append("  }")


def generate_ecu_uml(ecu_name, uml_lines, all_nodes):
    """Draw an ECU and all its ports, controllers, and switches in UML."""
    ecu_nodes = all_nodes["ecu_data"][ecu_name]

    for port_name in ecu_nodes["ports"]:
        draw_ports_uml(port_name, uml_lines, all_nodes)

    if ecu_nodes["controllers"]:
        draw_controllers_uml(ecu_nodes, all_nodes, uml_lines)

    if ecu_nodes["switches"]:
        draw_switches_uml(ecu_nodes, all_nodes, uml_lines)


def add_internally_connected_ports(uml_lines, all_nodes, vlan_id, src, dst, conn_id):
    """Draw intra-ECU port connection in UML, optionally filtered by VLAN ID."""
    if src in all_nodes["defined_nodes"] and dst in all_nodes["defined_nodes"]:
        uml_lines.append(f"[{src}] O--O [{dst}] : {conn_id}")
        if vlan_id is not None:
            for port in (src, dst):
                if all_nodes["node_types"].get(port) == "ecu_port":
                    all_nodes["internally_connected_ports"].add(port)


def generate_intra_ecu_uml(topology_connections, uml_lines, all_nodes, vlan_id):
    """Draw all intra-ECU port connections in UML."""
    for conn in topology_connections:
        conn_type = conn.root.type
        if not conn_type:
            continue

        mapping = get_mapping()
        if conn_type not in mapping:
            continue

        src_key, dst_key = mapping[conn_type]
        src = getattr(conn.root, src_key).name
        dst = getattr(conn.root, dst_key).name
        conn_id = conn.root.id
        add_internally_connected_ports(uml_lines, all_nodes, vlan_id, src, dst, conn_id)


def add_inter_ecu_uml(conn, all_nodes, uml_lines, vlan_id):
    """Draw inter-ECU port connection in UML, optionally filtered by VLAN ID."""
    if conn.type != "ecu_port_to_ecu_port":
        return

    ecu1_port = conn.ecu1_port.name
    ecu2_port = conn.ecu2_port.name
    conn_id = conn.id

    include_conn = False
    if vlan_id is None:
        include_conn = True
    else:
        if ecu1_port in all_nodes["internally_connected_ports"] or ecu2_port in all_nodes["internally_connected_ports"]:
            include_conn = True
    if include_conn:
        for port in (ecu1_port, ecu2_port):
            if port not in all_nodes["defined_nodes"]:
                uml_lines.insert(1, f"[{port}]")
                all_nodes["defined_nodes"].add(port)
        uml_lines.append(f"[{ecu1_port}] O--O [{ecu2_port}] : {conn_id}")


def parse_and_generate_uml(flync, vlan_id, options, ecus, connections):
    """Generate PlantUML diagram content for the given ECUs and connections."""
    uml_lines = [
        "@startuml",
        "skinparam linetype ortho",
        "skinparam ArrowThickness 1.5",
        "top to bottom direction",
        "skinparam RankSep 200",
        "skinparam PackageStyle rectangle",
        "",
    ]
    all_nodes = {}
    all_nodes["defined_nodes"] = set()
    all_nodes["node_types"] = dict()
    all_nodes["included_nodes"] = set()
    all_nodes["included_ecus"] = set()
    all_nodes["internally_connected_ports"] = set()
    all_nodes["macsec_nodes"] = dict()
    all_nodes["ptp_nodes"] = dict()
    all_nodes["qos_nodes"] = dict()
    all_nodes["ecu_data"] = dict()
    all_nodes["iface_info_nodes"] = dict()

    for ecu in ecus:
        ecu_name = ecu.name
        ecu_nodes = {
            "ports": set(),
            "controllers": {},
            "switches": {},
        }
        add_ecu_port_nodes(ecu.ports, ecu_nodes, all_nodes["node_types"])
        add_controller_nodes(ecu.controllers, vlan_id, ecu_nodes, all_nodes, options)
        add_switch_nodes(ecu.switches, vlan_id, ecu_nodes, all_nodes, options)

        if ecu_nodes["controllers"] or ecu_nodes["switches"]:
            all_nodes["included_ecus"].add(ecu_name)
            all_nodes["ecu_data"][ecu_name] = ecu_nodes

    for ecu_name in all_nodes["included_ecus"]:
        uml_lines.append(f'package "{ecu_name}" #WhiteSmoke {{')
        generate_ecu_uml(ecu_name, uml_lines, all_nodes)
        uml_lines.append("}")
        uml_lines.append("")

    for ecu_name in all_nodes["included_ecus"]:
        ecu_actual = flync.get_ecu_by_name(ecu_name)
        topology = ecu_actual.topology

        topology_connections = topology.connections
        generate_intra_ecu_uml(topology_connections, uml_lines, all_nodes, vlan_id)

    uml_lines.append("' Inter-ECU Connections")

    for conn in connections:
        add_inter_ecu_uml(conn, all_nodes, uml_lines, vlan_id)

    uml_lines.append("@enduml")
    return uml_lines


@app.command(
    help="Generate a UML representation of a given system configuration. Java (JRE 11+) must be on your PATH for PlantUML rendering to work."
)
def generate_system_uml(
    path: str = typer.Argument(help="Path to FLYNC config  directory containing ecus/"),
    output: str = typer.Option(
        "exports/uml/system_uml.puml",
        "--output",
        "-o",
        help="Output file path for UML diagram",
    ),
    vlan_id: Optional[int] = typer.Option(
        None,
        "--vlan-id",
        help="Filter diagram to only include components using this VLAN ID",
    ),
    show_macsec: Optional[bool] = typer.Option(
        False,
        "--macsec-info",
        help="Show the MACsec annotation if present in the ports",
    ),
    show_qos: Optional[bool] = typer.Option(
        False,
        "--qos-info",
        help="Show the QoS annotation if present in the ports",
    ),
    show_iface_info: Optional[bool] = typer.Option(
        False,
        "--iface-info",
        help="Show the Information of the Interface (VLANs, Multicast, IPs)",
    ),
    show_ptp_info: Optional[bool] = typer.Option(
        False,
        "--ptp-info",
        help="Show the PTP role if present in the port",
    ),
    target_ecu: Optional[str] = typer.Option(
        None,
        "--target-ecu",
        help="generate the system uml for only the target ECU,default is all",
    ),
):
    """Generate PlantUML diagram representing the system architecture with optional feature annotations."""
    loaded_ws = run_validation(path)
    options = []
    if show_macsec:
        options.append("macsec")
    if show_iface_info:
        options.append("iface")
    if show_ptp_info:
        options.append("ptp")
    if show_qos:
        options.append("qos")

    if target_ecu:
        find_target_ecu = loaded_ws.flync_model.get_ecu_by_name(target_ecu)
        ecus = [find_target_ecu]
        connections = []
    else:
        ecus = loaded_ws.flync_model.ecus
        connections = loaded_ws.flync_model.topology.system_topology.connections

    uml_lines = parse_and_generate_uml(loaded_ws.flync_model, vlan_id, options, ecus, connections)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(uml_lines))
        console.print(f"[green]UML diagram generated at {output_path}[/green]")
    except OSError as e:
        console.print(f"[red]Error writing UML file {output_path}: {str(e)}[/red]")
        raise typer.Exit(code=1)
