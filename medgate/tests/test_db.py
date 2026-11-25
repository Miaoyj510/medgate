from medgate import db


def test_connection_check_passes_on_sqlite():
    ok, detail = db.check_connection()
    assert ok is True, detail


def test_session_scope_can_query():
    with db.session_scope() as session:
        assert session.execute(__import__("sqlalchemy").text("SELECT 1")).scalar() == 1


def test_engine_is_reused():
    assert db.get_engine() is db.get_engine()
