"""ORM 模型。表结构按 PRD 9.2.1 的目录结构化层设计。

要点：
  · 目录层只走确定性查询，不进向量库（FR-CAT-02）；
  · 每条记录都带版本信息（catalog_version + effective_from/to），支撑「省份 × 就诊日期 × 年度」三维版本键；
  · 限价不公开的行 price_public=False 且 limit_price 为空，判定时输出「限价不可判定」，不估算。
"""

from .base import Base
from .catalog import (
    CatalogAlias,
    CatalogDiff,
    CatalogEntry,
    DrugProtocol,
    PriceStandard,
)

__all__ = [
    "Base",
    "CatalogAlias",
    "CatalogDiff",
    "CatalogEntry",
    "DrugProtocol",
    "PriceStandard",
]
