from flync.core.utils import yaml_io
from flync.model.flync_4_someip import SOMEIPServiceInterface


def test_ets():
    ets_high: SOMEIPServiceInterface = SOMEIPServiceInterface.model_validate(
        yaml_io.safe_load(open("./examples/flync_example/communication/someip/services/ets.flync.yaml", encoding="utf-8"))
    )
    assert ets_high.id == 0x101
    assert isinstance(ets_high, SOMEIPServiceInterface)
