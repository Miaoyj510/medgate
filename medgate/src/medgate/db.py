"""数据访问层：引擎与会话。

本增量只提供连接与健康自检；表结构在增量 1.2 随目录结构化层一并落地。
开发态默认 SQLite（免安装），生产形态为 PostgreSQL 16 + pgvector（PRD 13.8.3）。
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def ensure_sqlite_dir(url: str) -> None:
    """确保 SQLite 文件所在目录存在。

    全新检出（或 CI）时 data/ 目录并不在版本库里，SQLite 会直接报
    "unable to open database file"。这里在连接前把目录建出来。
    """
    if not url.startswith("sqlite"):
        return
    path_part = url.split("sqlite:///", 1)[-1]
    if not path_part or path_part == ":memory:":
        return
    target = Path(path_part)
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    """惰性创建引擎：导入模块不连库，测试与 CLI 才触发连接。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
        if settings.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False}
            ensure_sqlite_dir(settings.database_url)
        _engine = create_engine(settings.database_url, **kwargs)  # type: ignore[arg-type]
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务边界：正常提交，异常回滚。"""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> tuple[bool, str]:
    """连通性自检：返回 (是否连通, 说明)。用于健康检查与启动自检。"""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def init_db() -> None:
    """建表（增量 1.2 起有实际表结构）。生产环境用迁移工具接管，不在运行时建表。"""
    from .models import Base

    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    """删表，仅供开发与测试。"""
    from .models import Base

    Base.metadata.drop_all(get_engine())


def dispose_engine() -> None:
    """释放连接池（测试收尾用）。"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
