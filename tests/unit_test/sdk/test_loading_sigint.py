"""Tests for the Ctrl+C shutdown policy installed on workspace load pool workers."""

import signal

import pytest

from flync.sdk.workspace._loading import (
    _configure_pool_worker,
    _force_exit_pool_worker_on_sigint,
)


def test_configure_pool_worker_installs_sigint_handler():
    """Pool workers exit immediately (130) on Ctrl+C without a traceback."""
    previous = signal.getsignal(signal.SIGINT)
    try:
        _configure_pool_worker()
        assert signal.getsignal(signal.SIGINT) is _force_exit_pool_worker_on_sigint
    finally:
        signal.signal(signal.SIGINT, previous)


def test_force_exit_pool_worker_on_sigint_exits_with_130(monkeypatch):
    """The worker SIGINT handler exits hard with status 130."""
    exit_calls = []

    def fake_exit(code):
        exit_calls.append(code)
        raise SystemExit(code)

    monkeypatch.setattr("flync.sdk.workspace._loading.os._exit", fake_exit)

    with pytest.raises(SystemExit):
        _force_exit_pool_worker_on_sigint(2, None)

    assert exit_calls == [130]
