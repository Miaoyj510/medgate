from medgate import db


def test_connection_check_passes_on_sqlite():
    ok, detail = db.check_connection()
    assert ok is True, detail


def test_session_scope_can_query():
    with db.session_scope() as session:
        assert session.execute(__import__("sqlalchemy").text("SELECT 1")).scalar() == 1


def test_engine_is_reused():
    assert db.get_engine() is db.get_engine()


def test_engine_creates_missing_sqlite_directory(monkeypatch):
    """全新检出时 data/ 目录不存在，引擎应自动创建（CI 场景）。

    用仓库内自建目录，不依赖系统临时目录的写权限。
    """
    import shutil
    import uuid
    from pathlib import Path

    from medgate import config

    base = Path(__file__).resolve().parent.parent / ".testtmp" / uuid.uuid4().hex
    missing = base / "fresh-checkout" / "nested"
    try:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing / 'medgate.db'}")
        config.get_settings.cache_clear()
        db.dispose_engine()

        ok, detail = db.check_connection()
        assert ok is True, detail
        assert missing.exists()
    finally:
        db.dispose_engine()
        shutil.rmtree(base, ignore_errors=True)
