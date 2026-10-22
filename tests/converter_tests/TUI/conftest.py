"""Shared helpers for the flync_converter TUI tests.

This module is only test scaffolding. It loads the real built-in converters
into the TUI registry (once per worker) and exposes small helpers so each TUI
test file can drive the real ``FlyncTUI`` app with ``app.run_test()``.

"""

import asyncio
import threading
from contextlib import contextmanager

import pytest
from textual.widgets import Input, Select

from flync_converter.registry import registry
from flync_converter.utils import get_config_model


@pytest.fixture(scope="session", autouse=True)
def _load_converters():
    """Load the real built-in converters so the TUI panels have options."""
    registry.load_plugins()
    return registry


class Helpers:
    """Bundle of small helpers to drive the real TUI in tests."""

    @staticmethod
    def run(coro):
        """Run an async Textual test coroutine with ``asyncio.run``.

        Conversion threads started by the app can outlive the test body; they are joined
        before returning so none of them touches a closed event loop afterwards.
        """
        threads_before = set(threading.enumerate())
        try:
            return asyncio.run(coro)
        finally:
            for thread in set(threading.enumerate()) - threads_before:
                thread.join(timeout=5)

    @staticmethod
    def make_converter_class(name, config_model):
        """Build a minimal converter class whose config model resolves via get_config_model."""

        def _init(self, config=None):
            self.config = config

        cls = type(
            f"{name.title()}Converter",
            (object,),
            {
                "name": name,
                "config_model": config_model,
                "__init__": _init,
                "can_decode": lambda self: True,
                "encode": lambda self, source: None,
                "decode": lambda self: None,
            },
        )
        return cls

    @contextmanager
    def register(self, name, config_model):
        """Temporarily register a fake converter under ``name`` in the registry."""
        registry[name] = self.make_converter_class(name, config_model)()
        try:
            yield name
        finally:
            registry.pop(name, None)

    @staticmethod
    async def select_format(panel, fmt, pilot):
        """Select a format in a panel's #select and wait until its config fields
        have fully rebuilt (expected fields present, stale fields gone)."""
        import time as _time

        expected_names = set(get_config_model(fmt).model_fields)
        sel = panel.query_one("#select", Select)
        sel.value = fmt
        deadline = _time.monotonic() + 5.0
        while _time.monotonic() < deadline:
            container = panel.query_one("#fields")
            current_ids = {getattr(c, "id", None) for c in container.children if isinstance(c, (Input, Select))}
            expected_ids = {f"field-{panel.id}-{name}" for name in expected_names}
            if panel.converter_type == fmt and current_ids == expected_ids:
                return
            await pilot.pause()
            await asyncio.sleep(0.01)
        await pilot.pause()

    @staticmethod
    def set_config_path(panel, value):
        """Set the required ``config_path`` field of a panel (if it exists)."""
        inp = panel.query_one("#field-" + panel.id + "-config_path", Input)
        inp.value = value

    @staticmethod
    def log_text(log):
        """Return the current lines of a textual Log widget as plain text."""
        return "\n".join("".join(str(x) for x in line) for line in getattr(log, "lines", ()))

    @staticmethod
    async def wait_until(predicate, pilot, timeout=5.0, step=0.02):
        """Poll until ``predicate()`` is truthy or the timeout elapses."""
        import time as _time

        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if predicate():
                return True
            await pilot.pause()
            await asyncio.sleep(step)
        return predicate()


@pytest.fixture
def helpers():
    """Fixture exposing the shared TUI test helpers."""
    return Helpers()
