"""Keep inspection tests off the network and off Jev authority flags."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_jev_env(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_PRIMARY", raising=False)
    monkeypatch.delenv("JEV_DUAL_RUN", raising=False)
    monkeypatch.delenv("JEV_MODEL", raising=False)
    monkeypatch.delenv("JEV_API_URL", raising=False)
