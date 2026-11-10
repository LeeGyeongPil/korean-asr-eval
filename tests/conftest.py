"""Shared test setup: fixture paths relative to this file, and a network block."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any attempt to open a network connection fails the test (offline guarantee)."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access is not allowed in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def fixtures_dir() -> Path:
    return TESTS_DIR / "fixtures"


@pytest.fixture
def golden_dir() -> Path:
    return TESTS_DIR / "golden"
