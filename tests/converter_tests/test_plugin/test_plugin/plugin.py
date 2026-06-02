from flync_converter.base import BaseConverter
from flync_converter.hookspec import hookspec


class DummyConverter(BaseConverter):
    name = "dummy"

    def can_decode(self):
        return True

    def encode(self, source):
        return super().encode(source)

    def decode(self):
        return super().decode()


@hookspec
def register_converters():
    return [DummyConverter()]
