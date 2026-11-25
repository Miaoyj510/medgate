import pytest

from medgate import config, db


@pytest.fixture(autouse=True)
def _reset_settings():
    """每个用例前后重置配置单例与连接池，避免用例之间互相污染。"""
    config.get_settings.cache_clear()
    db.dispose_engine()
    yield
    config.get_settings.cache_clear()
    db.dispose_engine()
