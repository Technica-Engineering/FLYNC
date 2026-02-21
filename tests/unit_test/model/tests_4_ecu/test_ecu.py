import pytest
from flync.model.flync_4_someip import (
    SOMEIPServiceInterface,
)
from pathlib import Path
from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    ECUPort,
    MII,
    VLANEntry,
)


def test_ecu_parsing_from_dicts(
    metadata_entry, embedded_metadata_entry, ecu_port: ECUPort, MII_entry
):
    SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    kwargs = dict(
        name="test",
        topology={
            "connections": [
                {
                    "type": "ecu_port_to_switch_port",
                    "id": "1",
                    "ecu_port": "test_ecu_port",
                    "switch_port": "b",
                },
            ]
        },
        switches=[
            dict(
                meta=embedded_metadata_entry,
                name="a",
                ports=[
                    dict(
                        name="b",
                        silicon_port_no=1,
                        default_vlan_id=1,
                        mii_config=MII(mode="mac"),
                    ),
                    dict(name="c", silicon_port_no=2, default_vlan_id=1),
                ],
                vlans=[
                    VLANEntry(
                        name="vlan10", id=1, default_priority=1, ports=["a"]
                    )
                ],
            )
        ],
        controllers=[],
        ports=[
            ECUPort(
                name="test_ecu_port",
                mdi_config=BASET1(speed=100, role="slave"),
                mii_config=MII(mode="phy"),
            )
        ],
        ecu_metadata=metadata_entry,
    )
    # print(ecu_port_example)
    # assert isinstance(ecu_port_example,ECUPort)
    print("JOb", kwargs)
    ECU.model_validate(kwargs)

    # test if connections[0].ecu_port belongs to our created ECU
    # assert (id(ecu.topology.connections[0].root.ecu_port)
    #         in [id(e) for e in ecu.ports])
    # switches = Switch.model_validate(
    #         dict(
    #             name="a",
    #             ports=[
    #                 dict(name="b", silicon_port_no=1, default_vlan_id=1,
    #                      mii_config=MII(mode="MAC")),
    #                 dict(name="c", silicon_port_no=1, default_vlan_id=1)
    #             ],
    #             vlans=[
    #                 VLANEntry(name="vlan10", id=1, default_priority=1,
    #                 ports=["a"])
    #             ]
    #         )
    #     )


# def test_ecu_loding_without_general():
#     file_path = Path("examples/flync_basic_example")
#     with pytest.raises(ValueError):
#         ecu = ECU.load_from_folder(ecu_name="ecu1", base_dir=file_path)
