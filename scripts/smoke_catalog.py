"""目录导入冒烟：验证导入链路端到端行为（合并后必须通过）。

断言的是**期望行为**，不是退出码：示例种子文件里刻意留了 3 条异常样本，
导入器必须精确地把它们识别为异常、不入库，并且其余 21 条全部入库。

    python scripts/smoke_catalog.py
"""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "medgate" / "src"))

from medgate import config, db  # noqa: E402
from medgate.catalog import import_aliases, import_catalog  # noqa: E402
from medgate.models import CatalogEntry  # noqa: E402

SEED = ROOT / "medgate" / "seed" / "catalog_sample.csv"
ALIASES = ROOT / "medgate" / "seed" / "catalog_aliases.csv"
EXPECTED = {
    "total_rows": 24,
    "inserted": 21,
    "invalid": 3,
    "warnings": 1,
    "versions": {"NRDL-2024": 5, "NRDL-2025": 16},
}


def main() -> int:
    tmp = ROOT / "medgate" / ".testtmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True, exist_ok=True)
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'smoke.db'}"
    config.get_settings.cache_clear()
    db.dispose_engine()
    db.init_db()

    failures: list[str] = []
    try:
        with db.session_scope() as session:
            report = import_catalog(SEED, session)
            alias_report = import_aliases(ALIASES, session)

        for key, expected in EXPECTED.items():
            actual = {
                "total_rows": report.total_rows,
                "inserted": report.inserted,
                "invalid": report.invalid,
                "warnings": len(report.warnings),
                "versions": report.by_version,
            }[key]
            if actual != expected:
                failures.append(f"{key}: 期望 {expected}，实际 {actual}")

        error_fields = sorted({i.field for i in report.errors})
        if error_fields != ["duplicate", "effective_to", "generic_name"]:
            failures.append(f"异常字段集合不符：{error_fields}")

        with db.session_scope() as session:
            stored = session.query(CatalogEntry).count()
            if stored != EXPECTED["inserted"]:
                failures.append(f"库内条目数 {stored} ≠ {EXPECTED['inserted']}")
        if alias_report.inserted != 6:
            failures.append(f"别名导入 {alias_report.inserted} ≠ 6")
    finally:
        db.dispose_engine()
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print("冒烟未通过：")
        for f in failures:
            print("  -", f)
        return 1
    print("冒烟通过：24 行 → 入库 21 / 异常 3 / 警告 1，别名 6 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
