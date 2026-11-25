"""命令行入口。

    python -m medgate.cli init-db
    python -m medgate.cli import-catalog --file seed/catalog_sample.csv
    python -m medgate.cli import-aliases --file seed/catalog_aliases.csv
    python -m medgate.cli catalog-stats
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import case, func, select

from .catalog import import_aliases, import_catalog
from .config import get_settings
from .db import init_db, session_scope
from .logging_setup import setup_logging
from .models import CatalogAlias, CatalogEntry


def _cmd_init_db(args: argparse.Namespace) -> int:
    init_db()
    print("已建表。")
    return 0


def _cmd_import_catalog(args: argparse.Namespace) -> int:
    with session_scope() as session:
        report = import_catalog(
            args.file,
            session,
            default_version=args.version,
            default_effective_from=args.effective_from,
            default_effective_to=args.effective_to,
        )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.to_text())
    return 0 if report.ok else 2


def _cmd_import_aliases(args: argparse.Namespace) -> int:
    with session_scope() as session:
        report = import_aliases(args.file, session)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.to_text())
    return 0 if report.ok else 2


def _cmd_catalog_stats(args: argparse.Namespace) -> int:
    with session_scope() as session:
        rows = session.execute(
            select(
                CatalogEntry.catalog_version,
                func.count(CatalogEntry.id),
                func.coalesce(func.sum(case((CatalogEntry.price_public.is_(False), 1), else_=0)), 0),
            ).group_by(CatalogEntry.catalog_version)
        ).all()
        alias_count = session.scalar(select(func.count(CatalogAlias.id)))
    print(f"别名条目：{alias_count}")
    print("目录版本 | 条目数 | 限价不公开条数")
    for version, total, not_public in rows:
        print(f"{version} | {total} | {not_public or 0}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medgate", description="MedGate 双闸门平台 CLI")
    parser.add_argument("--log-level", default=None, help="覆盖 LOG_LEVEL")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="建表").set_defaults(func=_cmd_init_db)

    p = sub.add_parser("import-catalog", help="导入医保目录")
    p.add_argument("--file", required=True)
    p.add_argument("--version", default=None, help="文件缺目录版本列时使用")
    p.add_argument("--effective-from", default=None)
    p.add_argument("--effective-to", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_import_catalog)

    p = sub.add_parser("import-aliases", help="导入名称别名")
    p.add_argument("--file", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_import_aliases)

    sub.add_parser("catalog-stats", help="目录统计").set_defaults(func=_cmd_catalog_stats)
    return parser


def main(argv: list[str] | None = None) -> int:
    # 管道/重定向时按 UTF-8 输出，避免中文在非 GBK 控制台下乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level or get_settings().log_level)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
