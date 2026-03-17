from flync.core.utils.base_utils import check_obj_in_list


def get_switch_port_connected_component(
    comp,
    connected_components,
    new_connected_components,
    new_list,
    vlan,
):
    """Helper function to help validate multicast paths.

    Adds all the components connected to a switch
    port to the list of components that were
    not already there in the paths
    """
    conn = comp.connected_component
    if check_vlan_conn_valid(
        conn, connected_components, new_connected_components, vlan
    ):
        new_list.append(conn)
    mcast_ports = comp.get_vlan_connected_ports(vlan)
    for sport in mcast_ports:

        from flync.model.flync_4_ecu import SwitchPort

        sport_obj = SwitchPort.INSTANCES[sport]
        if (
            not check_obj_in_list(sport_obj, connected_components)
            and not check_obj_in_list(sport_obj, new_connected_components)
            and sport_obj.name != comp.name
        ):
            new_list.append(sport_obj)


def get_ecu_port_connected_component(
    comp, connected_components, new_connected_components, new_list, vlan
):
    """Helper function to help validate multicast paths.

    Adds all the components connected to a ECU
    Port to the list of components that were
    not already there in the paths
    """
    conn = comp.connected_components
    for conn1 in conn:
        if check_vlan_conn_valid(
            conn1, connected_components, new_connected_components, vlan
        ):
            new_list.append(conn1)


def get_controller_interface_connected_component(
    comp, connected_components, new_connected_components, new_list, vlan
):
    """Helper function to help validate multicast paths.

    Adds all the components connected to a controller
    interface to the list of components that were
    not already there in the paths
    """
    conn = comp.connected_component
    if check_vlan_conn_valid(
        conn, connected_components, new_connected_components, vlan
    ):
        new_list.append(conn)
    connected_interfaces = comp.get_other_interfaces()

    for iface in connected_interfaces:
        if (
            check_vlan_conn_valid(
                iface, connected_components, new_connected_components, vlan
            )
            and iface.name != conn.name
        ):
            new_list.append(iface)


def check_vlan_conn_valid(comp, list1, list2, vlan):
    """
    Helper to help compute multicast paths
    """
    flag = True
    if not comp:
        flag = False
    if check_obj_in_list(comp, list1):
        flag = False
    if check_obj_in_list(comp, list2):
        flag = False
    if comp.type == "switch_port" and not comp.is_part_of_vlan(vlan):
        flag = False
    if comp.type == "controller_interface" and not comp.is_part_of_vlan(vlan):
        flag = False
    return flag


def compute_path(vlan, interface):
    """
    Compute multicast path
    """
    connected_components = []
    new_connected_components = []
    connected_components.append(interface)

    direct_conn = interface.get_connected_components()
    if check_vlan_conn_valid(
        direct_conn, connected_components, new_connected_components, vlan
    ):
        new_connected_components.append(direct_conn)

    while len(new_connected_components) != 0:

        new_list = []
        for comp in new_connected_components:
            if comp._type == "switch_port":
                get_switch_port_connected_component(
                    comp,
                    connected_components,
                    new_connected_components,
                    new_list,
                    vlan,
                )

            if comp._type == "controller_interface":
                get_controller_interface_connected_component(
                    comp,
                    connected_components,
                    new_connected_components,
                    new_list,
                    vlan,
                )

            if comp._type == "ecu_port":
                get_ecu_port_connected_component(
                    comp,
                    connected_components,
                    new_connected_components,
                    new_list,
                    vlan,
                )

        connected_components.extend(new_connected_components)
        new_connected_components = new_list
    return connected_components


def serialize_components(list):
    """
    Displays the names of the components object
    present in the list
    """
    obj_str = "[ "
    for obj in list:
        obj_str = obj_str + (obj.name) + " , "
    obj_str = obj_str + "]"
    return obj_str
