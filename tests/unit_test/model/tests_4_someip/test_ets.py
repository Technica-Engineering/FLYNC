import pydantic_yaml

from flync.model.flync_4_someip import SOMEIPServiceInterface


def test_ets():
    ets_high: SOMEIPServiceInterface = pydantic_yaml.parse_yaml_file_as(
        SOMEIPServiceInterface,
        "./examples/flync_example/general/someip/services/ets.flync.yaml",
    )
    assert ets_high.id == 0x101
