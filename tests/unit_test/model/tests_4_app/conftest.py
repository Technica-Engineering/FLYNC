"""Factory fixtures shared by the application unit tests."""

import pytest

APP_NAME = "telemetry_app"

#: The service instance an app's consumer reference names; provider references vary from it per test.
SERVICE_REFERENCE = dict(service_id=0x101, instance_id=5, major_version=1)


@pytest.fixture
def app_data():
    """Return a factory for the *data* of an app consuming :data:`SERVICE_REFERENCE`.

    ``provider_difference`` is applied to the provider reference, so a caller flips between an app that
    provides the very instance it consumes (the default, no difference) and neighbouring instances.
    """

    def _build(**provider_difference) -> dict:
        return dict(
            name=APP_NAME,
            service_consumer_refs=[dict(SERVICE_REFERENCE)],
            service_provider_refs=[{**SERVICE_REFERENCE, **provider_difference}],
        )

    return _build
