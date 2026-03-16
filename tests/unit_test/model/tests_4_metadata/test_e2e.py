import pytest
from pydantic import ValidationError
from flync.model.flync_4_someip import (
    SOMEIPEventgroup,
    SOMEIPEvent,
    SOMEIPParameter,
    SOMEIPServiceInterface,
    SOMEIPConfig,
)

def test_e2e_config():
    e = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[],
        e2e={
            "profile": "AUTOSAR_Profile_1",
            "data_id": 0x12345678
        }
    )
    assert e.e2e.profile == "AUTOSAR_Profile_1"
    assert e.e2e.data_id == 0x12345678

def test_e2e_duplicate_data_id_in_profiles(metadata_entry):
    e1 = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[],
            e2e={
                "profile": "AUTOSAR_Profile_1",
                "data_id": 0x12345678
            }
        )
    e2 = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[],
            e2e={
                "profile": "AUTOSAR_Profile_2",
                "data_id": 0x12345678
            }
        )
    
    e3 = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[],
            e2e={
                "profile": "AUTOSAR_Profile_2",
                "data_id": 0x12345678
            }
        )
    
    with pytest.raises(ValidationError):
        
        ETS_01 = SOMEIPServiceInterface(
                    meta=metadata_entry,
                    name="a",
                    id=1,
                    events=[e1, e2],
                    eventgroups=[
                        SOMEIPEventgroup(
                            name="eg", id=1, events=[e1, e2], multicast_threshold=10
                        )
                    ],
                )

        ETS_02 = SOMEIPServiceInterface(
                    meta=metadata_entry,
                    name="a",
                    id=2,
                    events=[e3],
                    eventgroups=[
                        SOMEIPEventgroup(
                            name="eg", id=1, events=[e3], multicast_threshold=10
                        )
                    ],
                )
        
        SOMEIPConfig(
            services=[ETS_01, ETS_02]
        )
