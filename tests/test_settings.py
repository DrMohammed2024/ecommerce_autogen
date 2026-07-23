from app.config.settings import Settings, get_settings


def test_settings_load_local_environment() -> None:
    settings = Settings()

    assert settings.app_name == "ecommerce_autogen"
    assert settings.app_env == "development"
    assert settings.mock_mode is True
    assert settings.allow_external_actions is False
    assert settings.allow_payments is False


def test_database_uses_local_sqlite() -> None:
    settings = Settings()

    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_get_settings_returns_cached_instance() -> None:
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second