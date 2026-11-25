from medgate import config


def test_defaults_are_dev_and_sqlite():
    s = config.get_settings()
    assert s.app_env == "dev"
    assert s.llm_mode == "stub"
    assert s.is_sqlite is True
    # 未配置 API Key 时不得外发
    assert s.llm_enabled is False


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.setenv("MINIMAX_API_KEY", "dummy-key")
    config.get_settings.cache_clear()

    s = config.get_settings()
    assert s.app_env == "prod"
    assert s.log_level == "WARNING"
    assert s.llm_enabled is True


def test_invalid_values_are_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "unknown")
    config.get_settings.cache_clear()
    try:
        config.get_settings()
    except Exception:
        return
    raise AssertionError("非法 APP_ENV 应当被拒绝")


def test_public_fingerprint_hides_secret(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "super-secret-value")
    config.get_settings.cache_clear()
    s = config.get_settings()
    fingerprint = s.public_fingerprint()
    assert "super-secret-value" not in str(fingerprint)
    assert fingerprint["minimax_key_set"] is True
