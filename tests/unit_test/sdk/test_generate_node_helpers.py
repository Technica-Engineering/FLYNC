import shutil
from typing import Annotated, Optional

import pytest
from approvaltests import Union
from pydantic import Field

from flync.core.annotations.external import External
from flync.model import FLYNCBaseModel
from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_ecu import ECU, Controller, ECUPort
from flync.model.flync_4_ecu.internal_topology import (
    ECUPortToSwitchPort,
    SwitchPortToControllerInterface,
)
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_ecu.switch import Switch
from flync.model.flync_4_signal.frame import CANFDFrame, CANFrame
from flync.sdk.context.workspace_config import ListObjectsMode, WorkspaceConfiguration
from flync.sdk.helpers import generation_helpers as generation_helpers_util
from flync.sdk.helpers.generation_helpers import (
    Factory,
    FLYNCFactory,
    generate_external_node,
    generate_node,
)
from flync.sdk.utils.field_utils import get_field_name_from_alias
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.sdk.workspace.ids import ObjectId


@pytest.mark.parametrize(
    "node_type, override_values",
    [
        pytest.param(
            ECU,
            {"controllers": [{"lin_interfaces": [{"name": "lin_inter1"}]}]},
            id="ECU",
        ),
        pytest.param(
            Controller,
            {"lin_interfaces": [{"name": "lin_inter2"}]},
            id="Controller",
        ),
    ],
)
def test_generate_external_node_scaffold(node_type, override_values, tmp_path):
    """Scaffolding a node exercises the factory/generate path (Factory.build,
    list-field generation, name assignment) and writes it to disk."""
    output_path = tmp_path / f"generated_{node_type.__name__}"
    generate_external_node(node_type, output_path, workspace_config=None, **override_values)

    produced = list(output_path.rglob("*.yaml")) + list(output_path.rglob("*.yml"))
    assert produced, f"expected generate_external_node to write files for {node_type.__name__}"


GENERATE_NODE_PARAMS = [
    pytest.param(
        ["ecus.eth_ecu.ports"],
        "ports",
        ".ports",
        ECUPort,
        "test_port",
        id="ECUPort",
    ),
    pytest.param(
        ["ecus.eth_ecu.ports"],
        "ports",
        ".ports",
        ECUPort,
        "test_port2",
        id="ECUPort",
    ),
]


@pytest.mark.no_xdist
@pytest.mark.parametrize("node_paths,field,extra_field,expected_type,generated_name", GENERATE_NODE_PARAMS)
def test_generate_node_add_to_list(
    get_flync_example_path,
    tmp_path,
    node_paths,
    field,
    extra_field,
    expected_type,
    generated_name,
):
    """
    Generate a node and add it to an existing list field on a parent model.
    Verifies the node appears in the workspace, on disk, and persists after reload.
    """
    workspace_path = tmp_path / "test_generate"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("test_generate", workspace_path, config)

    # The generated node should be attached to ecus.eth_ecu.<field>
    parent_obj_id = ObjectId("ecus.eth_ecu")
    parent_obj = ws.get_object(parent_obj_id)
    original_count = len(getattr(parent_obj.model, field))

    assert generate_node(ws, node_paths, name=generated_name), "Node not generated"

    new_ws = FLYNCWorkspace.load_workspace("reload_test_generate", workspace_path, config)

    new_obj_id = ObjectId(f"{parent_obj_id}.{field}{extra_field}.{generated_name}")
    assert new_ws.has_object(new_obj_id), f"Expected {new_obj_id} to exist in workspace"

    new_node = new_ws.get_object(new_obj_id)
    assert isinstance(new_node.model, expected_type)

    parent_obj = new_ws.get_object(parent_obj_id)
    assert len(getattr(parent_obj.model, field)) == original_count + 1


@pytest.mark.parametrize(
    "node_paths,override_kwargs,expected_type,assertions",
    [
        (
            ["ecus.new"],
            {
                "name": "new",
                "ports": [{"name": "d", "mode": {"autonegotiation": True, "mode": "base_t1s"}}],
                # bus_ref / sender_frames must resolve against communication.channels: generate_node otherwise
                # scaffolds placeholder refs, which are dangling by construction.
                "controllers": [
                    {
                        "name": "new_controller",
                        "lin_interfaces": [
                            {
                                "name": "lin_inter",
                                "node_type": "slave",
                                "bus_ref": "BodyLIN",
                                "receiver_frames": [{"bus_ref": "BodyLIN", "frame_ref": 1}],
                            }
                        ],
                    }
                ],
            },
            ECU,
            [("name", "new")],
        ),
        (
            ["ecus.eth_ecu.ports.ports.override_port"],
            {"name": "override_port"},
            ECUPort,
            [("name", "override_port")],
        ),
        (
            ["ecus.high_performance_compute.topology.connections.ECUPortToSwitchPort"],
            {
                "id": "connn25",
                "switch": "hpc_switch1",
                "switch_port": "hpc_s1_p0",
                "ecu_port": "hpc1_p3",
            },
            ECUPortToSwitchPort,
            [
                ("id", "connn25"),
                ("switch", "hpc_switch1"),
                ("switch_port", "hpc_s1_p0"),
                ("ecu_port", "hpc1_p3"),
            ],
        ),
    ],
)
def test_generate_node_override_values(
    get_flync_example_path,
    tmp_path,
    node_paths,
    override_kwargs,
    expected_type,
    assertions,
):
    """Override values passed to generate_node should propagate to the generated model."""
    workspace_path = tmp_path / "test_override"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.NAME)
    ws: FLYNCWorkspace = FLYNCWorkspace.load_workspace("test_override", workspace_path, config)
    parent_id = node_paths[0].rsplit(".", 1)[0]
    old_children = ws.get_child_ids(parent_id)

    generate_node(ws, node_paths, **override_kwargs)

    # Reload the workspace to verify the node was persisted correctly
    ws2 = FLYNCWorkspace.load_workspace("test_override", workspace_path, config)
    sym_diff = set(ws2.get_child_ids(parent_id)) ^ set(old_children)
    assert len(sym_diff) > 0
    new_node = ws2.get_object(list(sym_diff)[0])
    assert isinstance(new_node.model, expected_type)

    for attr, expected_value in assertions:
        assert getattr(new_node.model, get_field_name_from_alias(type(new_node.model), attr)) == expected_value


def test_generate_node_set_attribue(get_flync_example_path, tmp_path):
    """``generate_node`` should populate an unset ``Optional External(FOLDER)`` field (``Switch.host_controller``)."""
    workspace_path = tmp_path / "test_set_attr"
    shutil.copytree(get_flync_example_path, workspace_path)

    # z1_switch1's host controller is removed for this test. The example's topology wires a
    # switch_port_to_host_controller_interface connection to it, so that connection has to go
    # too -- otherwise even a full reload fails validation before generate_node is reached.
    hc_dir = workspace_path / "ecus/zonal_platform1/switches/z1_switch1/switch_host_controller"
    shutil.rmtree(hc_dir)

    import yaml

    topo_file = workspace_path / "ecus/zonal_platform1/topology.flync.yaml"
    topo = yaml.safe_load(topo_file.read_text())
    topo["connections"] = [c for c in topo["connections"] if c.get("id") != "conn4"]
    topo_file.write_text(yaml.safe_dump(topo, sort_keys=False))

    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("test_set_attr", workspace_path, config)

    owner_model_id = "ecus.zonal_platform1.switches.z1_switch1"
    attr_fname = "host_controller"
    so = ws.get_object(owner_model_id)

    assert isinstance(so.model, Switch)
    assert so.model.host_controller is None

    generate_node(
        ws=ws,
        node_paths=[f"{owner_model_id}.{attr_fname}"],
        controller_metadata={
            "author": "Dev",
            "compatible_flync_version": {"version_schema": "semver", "version": "0.11.0"},
            "target_system": "flync_os",
        },
        ethernet_interfaces=[
            {
                "name": "z1_switch1_host_iface1",
                "interface_config": {
                    "mac_address": "00:11:03:03:01:01",
                    "virtual_interfaces": [
                        {
                            "name": "z1_sw_host_viface",
                            "vlanid": 50,
                            "addresses": [{"address": "10.0.50.100", "ipv4netmask": "255.255.255.0"}],
                        }
                    ],
                },
            }
        ],
    )

    ws_updated = FLYNCWorkspace.load_workspace("test_set_attr_updated", workspace_path, config)
    host_controller = ws_updated.get_object(f"{owner_model_id}.{attr_fname}").model
    assert host_controller.ethernet_interfaces[0].interface_config.mac_address == "00:11:03:03:01:01"


@pytest.mark.parametrize(
    "node_paths,override_kwargs,assertions,list_field_name,item_identifier",
    [
        pytest.param(
            ["ecus.zonal_platform2.topology"],
            {
                "connections": [
                    {
                        "type": "ecu_port_to_switch_port",
                        "id": "generated_conn1",
                        "switch_port": "z2_s1_p0",
                        "switch": "z2_switch1",
                        "ecu_port": "z2_p1",
                    },
                    {
                        "type": "switch_port_to_controller_interface",
                        "id": "generated_conn2",
                        "switch_port": "z2_s1_p1",
                        "controller_interface": "z2_c1_iface1",
                    },
                ]
            },
            {
                "generated_conn1": ECUPortToSwitchPort,
                "generated_conn2": SwitchPortToControllerInterface,
            },
            "connections",
            "id",
            id="connections-union",
        ),
    ],
)
def test_generate_node_append_to_union_list(
    get_flync_example_path,
    tmp_path,
    node_paths,
    override_kwargs,
    assertions,
    list_field_name,
    item_identifier,
):
    """
    Append several items to a list whose element type is a RootModel-wrapped discriminated union
    (``InternalConnectionUnion``) and verify each item is built as the matching concrete member,
    its override fields propagate, and it persists across a reload.
    """
    workspace_path = tmp_path / "test_union_generate"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.NAME)
    ws = FLYNCWorkspace.load_workspace("test_union_generate", workspace_path, config)

    oid = ObjectId(f"{node_paths[0]}.{list_field_name}")
    old_children = ws.get_child_ids(oid)
    original_count = len(old_children)
    items = override_kwargs[list_field_name]

    assert generate_node(ws, node_paths, **override_kwargs), "Node not generated"

    new_ws = FLYNCWorkspace.load_workspace("reload_test_union_generate", workspace_path, config)
    new_children = new_ws.get_child_ids(oid)

    # Exactly the requested items are added; nothing pre-existing is replaced or removed.
    added = set(new_children) - set(old_children)
    assert len(new_children) == original_count + len(items)
    assert len(added) == len(items)

    # Each new item must be built as the union member matching its discriminator
    # (``item_identifier``), with an expected concrete type from ``assertions``.
    actual = {getattr(new_ws.get_object(ObjectId(i)).model, item_identifier): new_ws.get_object(ObjectId(i)).model for i in added}
    assert set(actual) == set(assertions)
    for item_id, expected_type in assertions.items():
        assert isinstance(actual[item_id], expected_type)

    # The override fields of each provided item (other than the discriminator and the
    # item identifier) must be present on the generated member.
    for provided in items:
        model = actual[provided[item_identifier]]
        for key, value in provided.items():
            if key in ("type", item_identifier):
                continue
            assert getattr(model, get_field_name_from_alias(type(model), key)) == value


def test_generate_node_add_lin_interface_to_any_lin_union(get_flync_example_path, tmp_path):
    """
    Appending a LIN interface to ``Controller.lin_interfaces`` - a bare
    ``List[Annotated[Union[LINMaster, LINSlave], Field(discriminator="node_type")]]`` list -
    must select the concrete member matching ``node_type`` and persist across a reload.
    """
    workspace_path = tmp_path / "test_lin_generate"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.NAME)
    ws = FLYNCWorkspace.load_workspace("test_lin_generate", workspace_path, config)

    controller_id = ObjectId("ecus.zonal_platform1.controllers.z1_controller1")
    lin_oid = ObjectId(f"{controller_id}.lin_interfaces")
    parent = ws.get_object(controller_id)
    old_children = ws.get_child_ids(lin_oid)
    original_count = len(parent.model.lin_interfaces)

    new_interface = {
        "name": "new_lin_slave",
        "node_type": "slave",
        "bus_ref": "BodyLIN",
        "lin_protocol": "2.2A",
        "configured_nad": 1,
        "initial_nad": 1,
        "receiver_frames": [],
    }
    assert generate_node(ws, [str(controller_id)], lin_interfaces=[new_interface]), "Node not generated"

    new_ws = FLYNCWorkspace.load_workspace("reload_test_lin_generate", workspace_path, config)
    new_parent = new_ws.get_object(controller_id)
    added = set(new_ws.get_child_ids(lin_oid)) - set(old_children)

    assert len(new_parent.model.lin_interfaces) == original_count + 1
    assert len(added) == 1

    child = new_ws.get_object(ObjectId(added.pop()))
    assert isinstance(child.model, LINSlaveInterface)
    assert child.model.name == "new_lin_slave"
    assert child.model.bus_ref == "BodyLIN"
    assert child.model.configured_nad == 1

    # The pre-existing LIN master interface is untouched.
    masters = [i for i in new_parent.model.lin_interfaces if isinstance(i, LINMasterInterface)]
    assert len(masters) == 1
    assert masters[0].name == "body_lin_interface"


def test_factory_build_canbus_discriminated_frames():
    """
    Building a CANBus whose ``frames`` list element type is a bare discriminated union
    (``Annotated[Union[CANFrame, CANFDFrame], Field(discriminator="type")]``) must select the
    concrete member matching each ``type`` override.
    """
    bus = Factory.get_factory(CANBus).build(
        name="TestCAN",
        baud_rate=500000,
        fd_enabled=True,
        fd_baud_rate=2000000,
        frames=[
            {"name": "can1", "type": "can", "can_id": 0x100, "id_format": "standard_11bit", "length": 8},
            {"name": "fd1", "type": "can_fd", "can_id": 0x200, "id_format": "standard_11bit", "length": 64},
        ],
    )

    assert isinstance(bus, CANBus)
    assert [type(frame) for frame in bus.frames] == [CANFrame, CANFDFrame]
    assert bus.frames[0].name == "can1"
    assert bus.frames[0].can_id == 0x100
    assert bus.frames[1].name == "fd1"
    assert bus.frames[1].can_id == 0x200


def test_factory_list_element_annotation_helpers():
    """
    The list-element annotation helpers must unwrap ``Annotated`` metadata wrapped around the
    field (e.g. ``Annotated[Optional[List[X]], External(...)]``) and around the element
    (e.g. ``Annotated[Union[...], Field(discriminator=...)]``), while leaving non-list
    annotations untouched.
    """
    any_lin = Annotated[Union[LINMasterInterface, LINSlaveInterface], Field(discriminator="node_type")]

    # Annotated wrapping the field (covers the nested _strip_annotated unwrap).
    field_wrapped = Annotated[Optional[list[ECU]], External()]
    assert FLYNCFactory._list_element_annotation(field_wrapped) is ECU
    # A plain Optional list yields the element type directly.
    assert FLYNCFactory._list_element_annotation(Optional[list[ECU]]) is ECU
    # An element-level Annotated union is returned as-is for union-list detection.
    assert FLYNCFactory._list_element_annotation(list[any_lin]) is any_lin
    # A non-list annotation yields None.
    assert FLYNCFactory._list_element_annotation(ECU) is None


def test_factory_get_field_value_list_guards():
    """
    ``_get_field_value_list`` must reject a list whose element is neither a FLYNC model nor a
    union of models, and skip scaffolding an empty optional list (falling back to its default).
    """

    class WithPlainList(FLYNCBaseModel):
        things: list[str]

    class WithOptionalModelList(FLYNCBaseModel):
        extra: Optional[list[ECU]] = None

    # Plain (non-model) list element -> rejected (return False, None).
    assert FLYNCFactory._get_field_value_list(WithPlainList.model_fields["things"], []) == (False, None)
    # Empty optional list of a FLYNC model -> skipped (not scaffolded).
    assert FLYNCFactory._get_field_value_list(WithOptionalModelList.model_fields["extra"], []) == (False, None)


def test_patch_owner_scalar_and_unknown_fields():
    """
    ``__patch_owner`` must append list overrides in place, assign scalar overrides via a
    plain ``setattr`` fallback, and silently skip override keys that are not model fields.
    """

    class PatchTarget(FLYNCBaseModel):
        name: str
        count: int = 0
        tags: list[str] = []

    owner = PatchTarget(name="original")
    generated = PatchTarget(name="new", count=9, tags=["a", "b"])

    # List override -> appended in place (no setattr fallback).
    generation_helpers_util.__patch_owner(None, owner, generated, {"tags": ["a", "b"]})
    assert owner.tags == ["a", "b"]

    # Scalar overrides -> plain setattr fallback.
    generation_helpers_util.__patch_owner(None, owner, generated, {"name": "new", "count": 9})
    assert owner.name == "new"
    assert owner.count == 9

    # Unknown override key -> skipped without error.
    generation_helpers_util.__patch_owner(None, owner, generated, {"not_a_field": True})


def test_patch_existing_recurses_into_existing_object():
    """
    ``__patch_existing`` must recurse into an existing workspace object when the override value is a
    dict for a path that resolves to a loaded model, and report that it handled the patch.
    """

    class PatchTarget(FLYNCBaseModel):
        name: str
        count: int = 0

    class _ObjectStub:
        def __init__(self, model):
            self.model = model

    class _WorkspaceStub:
        def __init__(self, nested_model):
            self._nested = nested_model

        def has_object(self, oid):
            return str(oid) == "patch.target"

        def get_object(self, oid):
            return _ObjectStub(self._nested)

    nested = PatchTarget(name="inner")
    owner = PatchTarget(name="owner")
    generated = PatchTarget(name="generated", count=7)

    handled = generation_helpers_util.__patch_existing(
        _WorkspaceStub(nested),
        owner,
        "name",
        generated,
        {"name": "generated"},
        "patch.target",
    )
    assert handled is True
    # The existing object's matching field was updated in place (via the recursive __patch_owner).
    assert nested.name == "generated"
