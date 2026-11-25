"""医保目录导入器与导入校验报告。

对应 PRD 第 1 周 D1—D3：把目录 Excel/CSV 灌进结构化层，并产出一份能说清
「有多少条、多少条异常、异常在哪」的报告。

纪律：
  · 目录限价不公开的行，price_public=False 且不保存任何价格值，判定时输出「限价不可判定」（FR-COST-03 / HB-2）；
  · 缺必填字段、日期倒置等行**不入库**，只在报告里列为异常，不静默丢弃；
  · 重复行保留首条并报告，不覆盖；
  · 重复导入同一文件是幂等的（更新既有条目，不产生重复行）。
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CatalogAlias, CatalogEntry

# 目录文件常见表头 → 内部字段
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "generic_name": ("通用名", "通用名称", "药品名称", "药品通用名称", "generic_name"),
    "dosage_form": ("剂型", "剂型名称", "dosage_form"),
    "spec": ("规格", "规格型号", "剂型规格", "spec"),
    "class_flag": ("甲乙类", "医保目录类别", "目录类别", "class_flag"),
    "restriction_text": ("医保支付范围", "限定支付范围", "支付范围", "备注", "restriction_text"),
    "limit_price": ("支付标准", "价格", "限价", "limit_price"),
    "price_public": ("限价是否公开", "支付标准是否公开", "price_public"),
    "protocol_period": ("协议期", "协议有效期", "protocol_period"),
    "catalog_version": ("目录版本", "版本", "catalog_version"),
    "effective_from": ("生效日期", "开始日期", "执行日期", "effective_from"),
    "effective_to": ("失效日期", "结束日期", "废止日期", "effective_to"),
    "source_ref": ("数据来源", "来源", "source_ref"),
}
REQUIRED_FIELDS = ("generic_name", "dosage_form", "spec", "class_flag", "catalog_version",
                   "effective_from", "effective_to")
TRUE_WORDS = {"是", "公开", "有", "true", "yes", "y", "1"}
FALSE_WORDS = {"否", "不公开", "无", "false", "no", "n", "0"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class RowIssue:
    """单行问题。level: error（不入库）/ warning（入库但需人工关注）。"""

    row_no: int
    level: str
    field: str
    message: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"row_no": self.row_no, "level": self.level, "field": self.field,
                "message": self.message, "raw": self.raw}


@dataclass
class ImportReport:
    source: str
    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0
    by_version: dict[str, int] = field(default_factory=dict)
    issues: list[RowIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[RowIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[RowIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return self.invalid == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "total_rows": self.total_rows,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "by_version": self.by_version,
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_text(self) -> str:
        lines = [
            f"来源：{self.source}",
            f"总行数：{self.total_rows}　入库：{self.inserted}　更新：{self.updated}　"
            f"跳过：{self.skipped}　异常：{self.invalid}",
        ]
        if self.by_version:
            lines.append("按版本：" + "，".join(f"{k}={v}" for k, v in sorted(self.by_version.items())))
        if self.issues:
            lines.append("异常清单：")
            for i in self.issues:
                lines.append(f"  第{i.row_no}行 [{i.level}] {i.field}：{i.message}")
        lines.append("结论：" + ("全部通过" if self.ok else f"存在 {self.invalid} 条异常，未入库"))
        return "\n".join(lines)


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    """读取目录文件。支持 .csv 与 .xlsx（真实医保目录附件为 Excel）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"目录文件不存在：{p}")
    suffix = p.suffix.lower()
    if suffix == ".csv":
        with p.open("r", encoding="utf-8-sig", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    if suffix in {".xlsx", ".xlsm"}:
        from openpyxl import load_workbook

        wb = load_workbook(p, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        out: list[dict[str, Any]] = []
        for raw in rows[1:]:
            if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                continue
            out.append({header[i]: raw[i] for i in range(len(header))})
        wb.close()
        return out
    raise ValueError(f"不支持的文件类型：{suffix}（支持 .csv / .xlsx）")


def _normalize_header(name: str) -> str | None:
    key = str(name).strip().replace(" ", "")
    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if key == alias.replace(" ", ""):
                return field_name
    return None


def _map_row(raw: dict[str, Any]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for key, value in raw.items():
        field_name = _normalize_header(key)
        if field_name is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        mapped[field_name] = value
    return mapped


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip()
    if DATE_RE.match(text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    for fmt in ("%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _norm_key(name: str, dosage_form: str, spec: str) -> str:
    return "|".join(x.strip() for x in (name, dosage_form, spec))


def validate_row(row: dict[str, Any], row_no: int) -> list[RowIssue]:
    """单行校验。返回问题列表；出现 error 级问题则该行不入库。"""
    issues: list[RowIssue] = []
    for required in REQUIRED_FIELDS:
        value = row.get(required)
        if value in (None, ""):
            issues.append(RowIssue(row_no, "error", required, "缺少必填字段", row))

    eff_from = _parse_date(row.get("effective_from"))
    eff_to = _parse_date(row.get("effective_to"))
    if row.get("effective_from") not in (None, "") and eff_from is None:
        issues.append(RowIssue(row_no, "error", "effective_from",
                               f"生效日期无法解析：{row.get('effective_from')!r}", row))
    if row.get("effective_to") not in (None, "") and eff_to is None:
        issues.append(RowIssue(row_no, "error", "effective_to",
                               f"失效日期无法解析：{row.get('effective_to')!r}", row))
    if eff_from and eff_to and eff_from > eff_to:
        issues.append(RowIssue(row_no, "error", "effective_to",
                               f"生效日期 {eff_from} 晚于失效日期 {eff_to}", row))

    class_flag = str(row.get("class_flag") or "").strip()
    if class_flag and class_flag not in {"甲", "乙"}:
        issues.append(RowIssue(row_no, "error", "class_flag",
                               f"甲乙类只能是「甲」或「乙」，收到 {class_flag!r}", row))

    limit_price = _parse_float(row.get("limit_price"))
    price_public = _parse_bool(row.get("price_public"))
    if row.get("limit_price") not in (None, "") and limit_price is None:
        issues.append(RowIssue(row_no, "error", "limit_price",
                               f"支付标准无法解析为数字：{row.get('limit_price')!r}", row))
    if limit_price is not None and limit_price < 0:
        issues.append(RowIssue(row_no, "error", "limit_price", "支付标准不能为负", row))
    if price_public is False and limit_price is not None:
        issues.append(RowIssue(row_no, "warning", "limit_price",
                               "该条目限价不公开，文件中的价格值已忽略，判定时输出「限价不可判定」", row))
    if price_public is None and limit_price is not None:
        issues.append(RowIssue(row_no, "warning", "price_public",
                               "未标注限价是否公开，按公开处理", row))

    restriction = row.get("restriction_text")
    if isinstance(restriction, str) and len(restriction) > 1000:
        issues.append(RowIssue(row_no, "error", "restriction_text",
                               "限定支付范围文本超长（>1000 字符）", row))
    return issues


def _to_entry(row: dict[str, Any]) -> CatalogEntry:
    price_public = _parse_bool(row.get("price_public"))
    limit_price = _parse_float(row.get("limit_price"))
    if price_public is False:
        limit_price = None          # 限价不公开 → 不保留任何价格值
    elif price_public is None:
        price_public = True
    protocol = row.get("protocol_period")
    return CatalogEntry(
        catalog_version=str(row.get("catalog_version") or "").strip(),
        effective_from=_parse_date(row.get("effective_from")),
        effective_to=_parse_date(row.get("effective_to")),
        generic_name=str(row.get("generic_name") or "").strip(),
        dosage_form=str(row.get("dosage_form") or "").strip(),
        spec=str(row.get("spec") or "").strip(),
        class_flag=str(row.get("class_flag") or "").strip(),
        restriction_text=(str(row["restriction_text"]).strip()
                          if row.get("restriction_text") else None),
        limit_price=limit_price,
        price_public=bool(price_public),
        protocol_period=(str(protocol).strip() if protocol else None),
        source_ref=(str(row["source_ref"]).strip() if row.get("source_ref") else None),
    )


def import_catalog(
    path: str | Path,
    session: Session,
    *,
    default_version: str | None = None,
    default_effective_from: str | None = None,
    default_effective_to: str | None = None,
) -> ImportReport:
    """导入目录文件并产出校验报告。

    幂等：同一文件重复导入不会产生重复条目（按业务唯一键 upsert）。
    """
    report = ImportReport(source=str(path))
    rows = read_rows(path)
    seen: dict[str, int] = {}

    for idx, raw_row in enumerate(rows, start=2):   # 2 = 表头之后的第一行
        report.total_rows += 1
        row = _map_row(raw_row)
        if default_version and not row.get("catalog_version"):
            row["catalog_version"] = default_version
        if default_effective_from and not row.get("effective_from"):
            row["effective_from"] = default_effective_from
        if default_effective_to and not row.get("effective_to"):
            row["effective_to"] = default_effective_to

        issues = validate_row(row, idx)
        report.issues.extend(issues)
        if any(i.level == "error" for i in issues):
            report.invalid += 1
            continue

        key = "|".join([
            str(row.get("catalog_version") or ""),
            row["generic_name"], row["dosage_form"], row["spec"],
        ])
        if key in seen:
            report.issues.append(RowIssue(idx, "error", "duplicate",
                                          f"与第 {seen[key]} 行重复（通用名+剂型规格相同），保留首条",
                                          row))
            report.invalid += 1
            continue
        seen[key] = idx

        entry = _to_entry(row)
        existing = session.scalars(
            select(CatalogEntry).where(
                CatalogEntry.catalog_version == entry.catalog_version,
                CatalogEntry.generic_name == entry.generic_name,
                CatalogEntry.dosage_form == entry.dosage_form,
                CatalogEntry.spec == entry.spec,
            )
        ).first()
        if existing is None:
            session.add(entry)
            report.inserted += 1
            report.by_version[entry.catalog_version] = report.by_version.get(entry.catalog_version, 0) + 1
        else:
            for attr in ("effective_from", "effective_to", "class_flag", "restriction_text",
                         "limit_price", "price_public", "protocol_period", "source_ref"):
                setattr(existing, attr, getattr(entry, attr))
            report.updated += 1
    session.flush()
    return report


def import_aliases(path: str | Path, session: Session) -> ImportReport:
    """导入名称别名表（院内名 / 商品名 → 通用名 + 剂型规格）。"""
    report = ImportReport(source=str(path))
    for idx, raw_row in enumerate(read_rows(path), start=2):
        report.total_rows += 1
        alias_type = str(raw_row.get("别名类型") or raw_row.get("alias_type") or "").strip()
        alias_name = str(raw_row.get("别名") or raw_row.get("alias_name") or "").strip()
        generic_name = str(raw_row.get("通用名") or raw_row.get("generic_name") or "").strip()
        dosage_form = str(raw_row.get("剂型") or raw_row.get("dosage_form") or "").strip()
        spec = str(raw_row.get("规格") or raw_row.get("spec") or "").strip()
        if not alias_name or not generic_name:
            report.issues.append(RowIssue(idx, "error", "alias_name",
                                          "别名与通用名均为必填", raw_row))
            report.invalid += 1
            continue
        exists = session.scalars(
            select(CatalogAlias).where(
                CatalogAlias.alias_type == alias_type,
                CatalogAlias.alias_name == alias_name,
                CatalogAlias.generic_name == generic_name,
            )
        ).first()
        if exists is None:
            session.add(CatalogAlias(
                alias_type=alias_type or "通用名",
                alias_name=alias_name,
                norm_key=_norm_key(alias_name, dosage_form, spec),
                generic_name=generic_name,
                dosage_form=dosage_form or None,
                spec=spec or None,
                source_ref=str(raw_row.get("来源") or "").strip() or None,
            ))
            report.inserted += 1
        else:
            report.updated += 1
    session.flush()
    return report
