"""Config resolution + fail-fast validation for execution-plane targets.

Regression guard: a mis-named storage env var (STORAGE_ACCOUNT_NAME set but the
code reading STORAGE_ACCOUNT_URL) used to silently fall back to a decommissioned
demo account whose firewalled private endpoint hangs every blob write — the
POST /api/run never returns and the UI's sample cards spin forever. These tests
lock in: (1) both env spellings resolve, (2) name derives the URL, (3) neither
set fails fast at startup instead of hanging at runtime.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _restore_config_after_test():
    """Reloading config in these tests mutates the shared module singleton.
    Restore it to the real-environment state on teardown so later test modules
    (e.g. test_execution_store) don't inherit a polluted settings object."""
    yield
    import apps.orchestrator.config as config
    importlib.reload(config)


def _fresh_settings(monkeypatch, **env):
    """Reload config with a clean slice of the storage/cosmos env."""
    for k in ("STORAGE_ACCOUNT_URL", "STORAGE_ACCOUNT_NAME", "COSMOS_ENDPOINT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import apps.orchestrator.config as config
    return importlib.reload(config)


def test_storage_url_wins_when_both_set(monkeypatch):
    config = _fresh_settings(
        monkeypatch,
        STORAGE_ACCOUNT_URL="https://sturl.blob.core.windows.net",
        STORAGE_ACCOUNT_NAME="stname",
        COSMOS_ENDPOINT="https://c.documents.azure.com:443/",
    )
    assert config.settings.storage_account_url == "https://sturl.blob.core.windows.net"


def test_storage_name_derives_url(monkeypatch):
    config = _fresh_settings(
        monkeypatch,
        STORAGE_ACCOUNT_NAME="stderived",
        COSMOS_ENDPOINT="https://c.documents.azure.com:443/",
    )
    assert config.settings.storage_account_url == "https://stderived.blob.core.windows.net"


def test_no_hardcoded_demo_account_default(monkeypatch):
    config = _fresh_settings(
        monkeypatch,
        COSMOS_ENDPOINT="https://c.documents.azure.com:443/",
    )
    # Blank, NOT a fallback to a specific decommissioned account.
    assert config.settings.storage_account_url == ""


def test_validate_fails_fast_on_missing_storage(monkeypatch):
    config = _fresh_settings(
        monkeypatch,
        COSMOS_ENDPOINT="https://c.documents.azure.com:443/",
    )
    with pytest.raises(RuntimeError, match="STORAGE_ACCOUNT_URL"):
        config.validate_runtime_settings()


def test_validate_passes_when_storage_present(monkeypatch):
    config = _fresh_settings(
        monkeypatch,
        STORAGE_ACCOUNT_NAME="stok",
        COSMOS_ENDPOINT="https://c.documents.azure.com:443/",
    )
    # Should not raise.
    config.validate_runtime_settings()
