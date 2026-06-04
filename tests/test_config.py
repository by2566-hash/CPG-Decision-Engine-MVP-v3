import pytest
from pydantic import ValidationError

from src.decision_engine.config import Settings


def test_settings_does_not_require_shopline_secret_for_db_only_deploy(monkeypatch):
    monkeypatch.delenv("ALLOW_PLACEHOLDER_SECRETS", raising=False)

    settings = Settings(
        postgres_dsn="postgresql://postgres:secure@example.com:5432/smart_brain",
        redis_url="redis://:secure@example.com:6379/0",
        api_key="java-python-shared-key",
    )

    assert settings.shopline_app_secret == "replace_me"
    assert settings.enable_shopline_webhook is False


def test_settings_requires_shopline_secret_when_webhook_enabled(monkeypatch):
    monkeypatch.delenv("ALLOW_PLACEHOLDER_SECRETS", raising=False)

    with pytest.raises(ValidationError, match="SHOPLINE_APP_SECRET"):
        Settings(
            postgres_dsn="postgresql://postgres:secure@example.com:5432/smart_brain",
            redis_url="redis://:secure@example.com:6379/0",
            api_key="java-python-shared-key",
            enable_shopline_webhook=True,
        )
