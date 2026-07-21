import pytest

from wandb_monitor import format_duration, load_config_from_environment


def test_monitor_module_loads_without_optional_dependencies_or_network_access():
    assert format_duration(59) == "59s"
    assert format_duration(120) == "2min"
    assert format_duration(3720) == "1h 2min"


def test_load_monitor_config_from_environment(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "test-api-key")
    monkeypatch.setenv("WANDB_ENTITY", "test-entity")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("WANDB_MONITOR_INTERVAL_SECONDS", "30")

    config = load_config_from_environment()

    assert config.api_key == "test-api-key"
    assert config.entity == "test-entity"
    assert config.discord_webhook_url == "https://example.com/webhook"
    assert config.check_interval_seconds == 30


@pytest.mark.parametrize("interval", ["invalid", "0", "-1"])
def test_load_monitor_config_rejects_invalid_intervals(monkeypatch, interval):
    monkeypatch.setenv("WANDB_API_KEY", "test-api-key")
    monkeypatch.setenv("WANDB_ENTITY", "test-entity")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("WANDB_MONITOR_INTERVAL_SECONDS", interval)

    with pytest.raises(ValueError):
        load_config_from_environment()
