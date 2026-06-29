from __future__ import annotations

from apie.config import resolve_config


def test_resolve_config_uses_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("APIE_API_KEY", "apie_sk_test_123")
    monkeypatch.setenv("APIE_BASE_URL", "https://api.apie.sh")

    config = resolve_config({"agent": {"key": "agent", "name": "Agent"}})

    assert config.api_key == "apie_sk_test_123"
    assert config.base_url == "https://api.apie.sh"
    assert config.mode == "monitor"
    assert config.release_mode == "monitor"


def test_resolve_config_maps_legacy_mode(monkeypatch) -> None:
    monkeypatch.delenv("APIE_BASE_URL", raising=False)
    monkeypatch.setenv("APIE_API_KEY", "apie_sk_test_123")

    config = resolve_config({"agent": {"key": "agent", "name": "Agent"}, "mode": "enforce"})
    assert config.mode == "enforce"
    assert config.release_mode == "enforce"
    assert config.base_url == "http://localhost:3000"


def test_resolve_config_normalizes_legacy_guard(monkeypatch) -> None:
    monkeypatch.setenv("APIE_API_KEY", "apie_sk_test_123")

    config = resolve_config(
        {"agent": {"key": "agent", "name": "Agent"}, "releaseMode": "guard"}
    )
    assert config.mode == "enforce"
