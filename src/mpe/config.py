"""Typed settings loaded from ``config/*.yaml``."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


class PaperTrading(BaseModel):
    enabled: bool = True
    real_trading_enabled: bool = False

    @model_validator(mode="after")
    def _paper_only(self):
        if self.real_trading_enabled:
            raise ValueError("real_trading_enabled must be false: this system only paper-trades")
        return self


class Http(BaseModel):
    timeout_s: float = 30
    max_retries: int = 5
    backoff_base_s: float = 1.0
    backoff_max_s: float = 60
    user_agent: str = "TimeBalance-research/0.1"


class Availability(BaseModel):
    stock_close_delay_minutes: int = 30
    fx_close_delay_minutes: int = 30
    polymarket_history_latency_seconds: int = 60


class Selection(BaseModel):
    target_open: int = 35
    target_resolved: int = 12
    min_liquidity_open: float = 20_000
    min_volume_open: float = 100_000
    min_volume_resolved: float = 250_000
    min_history_days: int = 14
    resolved_lookback_days: int = 365
    max_candidates_per_scan: int = 600
    exclude_neg_risk: bool = True


class Trades(BaseModel):
    max_pages_per_market: int = 5


class Polymarket(BaseModel):
    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"
    data_url: str = "https://data-api.polymarket.com"
    history_interval: str = "1h"
    history_window_days: int = 14
    daily_request_budget: int = 20_000
    min_request_interval_s: float = 0.05
    selection: Selection = Field(default_factory=Selection)
    trades: Trades = Field(default_factory=Trades)


class Stocks(BaseModel):
    provider: str = "yfinance"
    calendar: str = "XNYS"
    backfill_start: str = "2010-01-01"
    outlier_z: float = 8.0
    stale_after_sessions: int = 2


class Settings(BaseModel):
    database_path: str = "data/mpe.sqlite3"
    research_database_path: str = "data/research.sqlite3"  # M2 experiment results (separate file)
    raw_dump_dir: str = "data/raw"
    paper_trading: PaperTrading = Field(default_factory=PaperTrading)
    http: Http = Field(default_factory=Http)
    availability: Availability = Field(default_factory=Availability)
    polymarket: Polymarket = Field(default_factory=Polymarket)
    stocks: Stocks = Field(default_factory=Stocks)

    def resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else ROOT / p


class WatchItem(BaseModel):
    symbol: str
    name: str | None = None
    asset_type: str
    exchange: str | None = None
    currency: str = "USD"


class AssetsConfig(BaseModel):
    watchlist: list[WatchItem]
    fx: list[WatchItem] = Field(default_factory=list)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def load_settings(path: Path | None = None) -> Settings:
    """Settings from YAML. ``MPE_DATABASE`` / ``MPE_RESEARCH_DATABASE`` override the database paths."""
    data = _load(path or CONFIG_DIR / "settings.yaml")
    if os.environ.get("MPE_DATABASE"):
        data["database_path"] = os.environ["MPE_DATABASE"]
    if os.environ.get("MPE_RESEARCH_DATABASE"):
        data["research_database_path"] = os.environ["MPE_RESEARCH_DATABASE"]
    return Settings.model_validate(data)


def load_assets(path: Path | None = None) -> AssetsConfig:
    return AssetsConfig.model_validate(_load(path or CONFIG_DIR / "assets.yaml"))
