"""医保目录结构化层（PRD 9.2.1）。

drug_catalog          目录条目主表：一行 = 一个 (目录版本, 通用名, 剂型规格)
drug_catalog_alias    名称别名与归一（院内名 / 商品名 → 通用名）
drug_protocol         协议期信息
price_standard        限价与价格版本
catalog_diff          版本间差异（由版本维护流程写入，见 FR-RULE-03）
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class CatalogEntry(Base):
    __tablename__ = "drug_catalog"
    __table_args__ = (
        UniqueConstraint(
            "catalog_version", "generic_name", "dosage_form", "spec",
            name="uq_catalog_entry",
        ),
        Index("ix_catalog_entry_name", "generic_name"),
        Index("ix_catalog_entry_version", "catalog_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_version: Mapped[str] = mapped_column(String(32))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    generic_name: Mapped[str] = mapped_column(String(128))
    dosage_form: Mapped[str] = mapped_column(String(64))
    spec: Mapped[str] = mapped_column(String(64))
    class_flag: Mapped[str] = mapped_column(String(4))          # 甲 / 乙
    restriction_text: Mapped[str | None] = mapped_column(Text)  # 限定支付范围（备注）
    limit_price: Mapped[float | None] = mapped_column(Float)    # 支付标准
    price_public: Mapped[bool] = mapped_column(Boolean, default=True)
    protocol_period: Mapped[str | None] = mapped_column(String(32))
    source_ref: Mapped[str | None] = mapped_column(String(256))

    protocol: Mapped["DrugProtocol"] = relationship(back_populates="entry", uselist=False)
    prices: Mapped[list["PriceStandard"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class CatalogAlias(Base):
    """名称归一：把院内名/商品名映射到目录通用名 + 剂型规格。

    归一失败时不猜测，返回候选集交人工确认（FR-CAT-06）。
    """

    __tablename__ = "drug_catalog_alias"
    __table_args__ = (
        UniqueConstraint("alias_type", "alias_name", "generic_name", name="uq_alias"),
        Index("ix_alias_norm_key", "norm_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alias_type: Mapped[str] = mapped_column(String(32))   # 通用名 / 商品名 / 院内名
    alias_name: Mapped[str] = mapped_column(String(128))
    norm_key: Mapped[str] = mapped_column(String(160))    # 归一后的匹配键
    generic_name: Mapped[str] = mapped_column(String(128))
    dosage_form: Mapped[str | None] = mapped_column(String(64))
    spec: Mapped[str | None] = mapped_column(String(64))
    source_ref: Mapped[str | None] = mapped_column(String(256))


class DrugProtocol(Base):
    """协议期药品的协议区间（FR-CAT-07）。"""

    __tablename__ = "drug_protocol"
    __table_args__ = (UniqueConstraint("catalog_entry_id", name="uq_protocol_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_entry_id: Mapped[int] = mapped_column(ForeignKey("drug_catalog.id", ondelete="CASCADE"))
    protocol_start: Mapped[date | None] = mapped_column(Date)
    protocol_end: Mapped[date | None] = mapped_column(Date)
    scope_text: Mapped[str | None] = mapped_column(Text)

    entry: Mapped["CatalogEntry"] = relationship(back_populates="protocol")


class PriceStandard(Base):
    """限价与价格版本（按 catalog_id + price_version + 省份）。"""

    __tablename__ = "price_standard"
    __table_args__ = (
        UniqueConstraint("catalog_entry_id", "price_version", "region_code", name="uq_price_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_entry_id: Mapped[int] = mapped_column(ForeignKey("drug_catalog.id", ondelete="CASCADE"))
    price_version: Mapped[str] = mapped_column(String(32))
    region_code: Mapped[str] = mapped_column(String(32))     # 省份或统筹区
    limit_price: Mapped[float | None] = mapped_column(Float)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)

    entry: Mapped["CatalogEntry"] = relationship(back_populates="prices")


class CatalogDiff(Base):
    """目录版本间差异（由版本维护流程写入，FR-RULE-03 / FR-CAT-04）。"""

    __tablename__ = "catalog_diff"
    __table_args__ = (UniqueConstraint("from_version", "to_version", "change_type", "item_key",
                                       name="uq_diff"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    change_type: Mapped[str] = mapped_column(String(16))     # added / removed / changed
    item_key: Mapped[str] = mapped_column(String(200))        # 通用名+剂型规格
    detail: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[date | None] = mapped_column(Date)
