from pathlib import Path

import pytest

from medgate import config, db
from medgate.catalog import import_aliases, import_catalog
from medgate.models import CatalogAlias, CatalogEntry

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
SAMPLE = SEED_DIR / "catalog_sample.csv"
ALIASES = SEED_DIR / "catalog_aliases.csv"


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'catalog.db'}")
    config.get_settings.cache_clear()
    db.dispose_engine()
    db.init_db()
    with db.session_scope() as s:
        yield s


def test_import_reports_counts_and_invalid_rows(session):
    report = import_catalog(SAMPLE, session)

    assert report.total_rows == 24
    assert report.inserted == 21
    assert report.invalid == 3
    assert report.ok is False

    fields = {(i.level, i.field) for i in report.issues}
    assert ("error", "generic_name") in fields        # 缺通用名
    assert ("error", "effective_to") in fields        # 日期倒置
    assert ("error", "duplicate") in fields           # 重复行
    assert ("warning", "limit_price") in fields       # 限价不公开却带价格


def test_invalid_rows_are_not_stored(session):
    import_catalog(SAMPLE, session)
    names = {c.generic_name for c in session.query(CatalogEntry).all()}
    assert "" not in names
    assert "维生素C片" not in names      # 日期倒置行不入库


def test_same_drug_across_versions_is_not_duplicate(session):
    import_catalog(SAMPLE, session)
    rows = session.query(CatalogEntry).filter(
        CatalogEntry.generic_name == "二甲双胍缓释片"
    ).all()
    assert len(rows) == 2
    assert {r.catalog_version for r in rows} == {"NRDL-2024", "NRDL-2025"}


def test_price_not_public_entry_keeps_no_price(session):
    import_catalog(SAMPLE, session)
    entry = session.query(CatalogEntry).filter(
        CatalogEntry.generic_name == "注射用重组人干扰素"
    ).one()
    assert entry.price_public is False
    assert entry.limit_price is None      # 不公开的限价不落库，判定时输出「限价不可判定」


def test_reimport_is_idempotent(session):
    first = import_catalog(SAMPLE, session)
    assert first.inserted == 21
    before = session.query(CatalogEntry).count()

    second = import_catalog(SAMPLE, session)
    assert second.inserted == 0
    assert second.updated == 21
    assert session.query(CatalogEntry).count() == before


def test_removal_case_exists_only_in_old_version(session):
    import_catalog(SAMPLE, session)
    versions = {
        r.catalog_version
        for r in session.query(CatalogEntry).filter(
            CatalogEntry.generic_name == "枯草杆菌二联活菌胶囊"
        ).all()
    }
    assert versions == {"NRDL-2024"}     # 2026 调出品，只在旧版本存在


def test_alias_import(session):
    report = import_aliases(ALIASES, session)
    assert report.inserted == 6
    alias = session.query(CatalogAlias).filter(
        CatalogAlias.alias_name == "立普妥"
    ).one()
    assert alias.generic_name == "阿托伐他汀钙片"
    assert alias.spec == "20mg"


def test_report_text_is_readable(session):
    report = import_catalog(SAMPLE, session)
    text = report.to_text()
    assert "总行数：24" in text
    assert "异常清单" in text
