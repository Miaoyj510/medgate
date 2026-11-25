"""配置层：所有可变项一律来自环境变量或 .env，不写死在业务代码里。

对应 PRD 13.8.4 PR-5（凭据外置）与 13.8.9（配置与凭据不得落入镜像）。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# medgate/ 目录（src/medgate/config.py -> medgate/）
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """应用配置。字段名即环境变量名（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 服务 ---
    app_env: str = Field(default="dev", description="dev / staging / prod")
    log_level: str = Field(default="INFO")
    api_port: int = Field(default=8080)

    # --- 存储 ---
    database_url: str = Field(
        default=f"sqlite:///{PROJECT_DIR / 'data' / 'medgate.db'}",
        description="SQLAlchemy 连接串；开发可用 sqlite，生产为 postgresql+psycopg",
    )
    redis_url: str = Field(default="", description="为空表示不启用队列与并发闸门")
    embedding_dim: int = Field(default=512)

    # --- 数据 ---
    seed_dir: str = Field(default="seed", description="目录 / 编码 / 规则种子目录")

    # --- 大模型（仅抽取、归类、说明三类辅助任务）---
    llm_mode: str = Field(default="stub", description="stub（不外发）/ api（真实调用）")
    minimax_api_key: str = Field(default="")
    minimax_base_url: str = Field(default="https://api.minimaxi.com/v1")
    minimax_model: str = Field(default="MiniMax-M2")
    minimax_timeout: float = Field(default=20.0)
    minimax_max_retries: int = Field(default=1)
    max_llm_concurrency: int = Field(default=2)
    llm_call_budget_per_case: int = Field(default=4)

    @field_validator("app_env")
    @classmethod
    def _check_app_env(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"dev", "staging", "prod"}:
            raise ValueError(f"APP_ENV 只能是 dev / staging / prod，收到 {v!r}")
        return v

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"LOG_LEVEL 非法：{v!r}")
        return v

    @field_validator("llm_mode")
    @classmethod
    def _check_llm_mode(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"stub", "api"}:
            raise ValueError(f"LLM_MODE 只能是 stub / api，收到 {v!r}")
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def llm_enabled(self) -> bool:
        """仅在明确配置了凭据且模式为 api 时才允许外发。"""
        return self.llm_mode == "api" and bool(self.minimax_api_key)

    @property
    def seed_path(self) -> Path:
        p = Path(self.seed_dir)
        return p if p.is_absolute() else (PROJECT_DIR / p)

    def public_fingerprint(self) -> dict[str, object]:
        """对外可暴露的配置摘要：只给指纹，不给明文凭据（PRD 13.8.9）。"""
        return {
            "app_env": self.app_env,
            "log_level": self.log_level,
            "database": self.database_url.split("://", 1)[0],
            "redis": "enabled" if self.redis_url else "disabled",
            "llm_mode": self.llm_mode,
            "llm_enabled": self.llm_enabled,
            "model": self.minimax_model if self.llm_enabled else "stub",
            "minimax_key_set": bool(self.minimax_api_key),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例。测试中用 get_settings.cache_clear() 重置。"""
    return Settings()
