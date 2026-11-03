"""SQLAlchemy models for the schema in the brief (§7.2).

Every price, size, cash and fee column is ``DecimalText`` (TEXT affinity). Every timestamp is
``UTCText`` (ISO-8601 ``...Z``). Model statistics are REAL. Deviations from the brief's DDL:

- ``assets.market_id`` points at ``markets`` (declared after it here; SQLite does not care).
- ``observations.trade_count`` added: the number of trades behind an aggregated volume figure.
- ``markets.event_id``, ``event_slug``, ``neg_risk``, ``selected``, ``first_seen_at`` and
  ``updated_at`` added, so the panel and the multi-outcome exclusion can be queried without
  parsing ``raw_json``. Every scanned market is stored; ``selected`` marks the panel.
- ``markets.fee_bps`` holds the Polymarket taker fee *rate* × 10,000 (fee = shares × rate × p ×
  (1 − p)), not a flat basis-point fee.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mpe.storage.types import DecimalText, UTCText


class Base(DeclarativeBase):
    pass


DEC = DecimalText
TS = UTCText


class Market(Base):
    __tablename__ = "markets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="polymarket")
    provider_market_id: Mapped[str] = mapped_column(Text, nullable=False)  # condition id
    slug = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    description = mapped_column(Text)
    market_type: Mapped[str] = mapped_column(Text, nullable=False)
    category = mapped_column(Text)
    event_id = mapped_column(Text)
    event_slug = mapped_column(Text)
    neg_risk = mapped_column(Integer)
    yes_token_id = mapped_column(Text)
    no_token_id = mapped_column(Text)
    resolution_rules = mapped_column(Text)
    resolution_source = mapped_column(Text)
    opening_time = mapped_column(TS)
    closing_time = mapped_column(TS)
    resolution_status: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_value = mapped_column(Text)
    fee_bps = mapped_column(DEC)
    selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selection_reason = mapped_column(Text)
    raw_json = mapped_column(Text)
    first_seen_at = mapped_column(TS)
    updated_at = mapped_column(TS)
    __table_args__ = (
        UniqueConstraint("provider", "provider_market_id"),
        CheckConstraint(
            "resolution_status IN ('open','closed','resolved','cancelled','disputed','ambiguous')",
            name="ck_markets_status",
        ),
    )


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    exchange = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    market_id = mapped_column(Integer, ForeignKey("markets.id"))
    outcome_side = mapped_column(Text)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    listed_at = mapped_column(TS)
    delisted_at = mapped_column(TS)
    meta_json = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("provider", "symbol"),
        CheckConstraint(
            "asset_type IN ('stock','etf','crypto','fx','index','pm_token')", name="ck_assets_type"
        ),
        CheckConstraint("outcome_side IN ('YES','NO') OR outcome_side IS NULL", name="ck_assets_side"),
    )


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    timestamp = mapped_column(TS, nullable=False)
    interval: Mapped[str] = mapped_column(Text, nullable=False)
    open = mapped_column(DEC)
    high = mapped_column(DEC)
    low = mapped_column(DEC)
    close = mapped_column(DEC)
    adj_close = mapped_column(DEC)
    volume = mapped_column(DEC)
    trade_count = mapped_column(Integer)
    bid = mapped_column(DEC)
    ask = mapped_column(DEC)
    bid_size = mapped_column(DEC)
    ask_size = mapped_column(DEC)
    liquidity = mapped_column(DEC)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ts = mapped_column(TS)
    retrieved_at = mapped_column(TS, nullable=False)
    available_at = mapped_column(TS, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality_flags = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("asset_id", "timestamp", "interval", "source", "version"),
        Index("ix_obs_asset_time", "asset_id", "interval", "timestamp"),
    )


class OrderBookSnapshot(Base):
    __tablename__ = "order_book_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    timestamp = mapped_column(TS, nullable=False)
    retrieved_at = mapped_column(TS, nullable=False)
    bids_json: Mapped[str] = mapped_column(Text, nullable=False)
    asks_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_book_asset_time", "asset_id", "timestamp"),)


class Feature(Base):
    __tablename__ = "features"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    timestamp = mapped_column(TS, nullable=False)
    available_at = mapped_column(TS, nullable=False)
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    feature_value = mapped_column(Float)
    feature_version: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("asset_id", "timestamp", "feature_name", "feature_version"),)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at = mapped_column(TS, nullable=False)
    notes = mapped_column(Text)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id = mapped_column(Integer, ForeignKey("experiments.id"))
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_size = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    code_version: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    inference_device = mapped_column(Text)
    started_at = mapped_column(TS, nullable=False)
    completed_at = mapped_column(TS)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error = mapped_column(Text)
    peak_ram_mb = mapped_column(Float)
    peak_vram_mb = mapped_column(Float)
    __table_args__ = (
        CheckConstraint("mode IN ('live','backtest','holdout','benchmark')", name="ck_runs_mode"),
        CheckConstraint("status IN ('running','succeeded','failed')", name="ck_runs_status"),
    )


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_runs.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    forecast_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at = mapped_column(TS, nullable=False)
    input_cutoff_timestamp = mapped_column(TS, nullable=False)
    target_timestamp = mapped_column(TS, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_unit: Mapped[str] = mapped_column(Text, nullable=False)
    forecast_values: Mapped[str] = mapped_column(Text, nullable=False)
    quantiles: Mapped[str] = mapped_column(Text, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    context_start_timestamp = mapped_column(TS, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    feature_version = mapped_column(Text)
    multivariate_group = mapped_column(Text)
    runtime_ms = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("model_run_id", "asset_id", "forecast_type", "input_cutoff_timestamp", "horizon"),
        Index("ix_fc_target", "asset_id", "forecast_type", "horizon", "target_timestamp"),
    )


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_id: Mapped[int] = mapped_column(Integer, ForeignKey("forecasts.id"), nullable=False)
    forecast_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(Text, nullable=False)
    direction = mapped_column(Text)
    reference_price = mapped_column(DEC, nullable=False)
    expected_return = mapped_column(Float)
    estimated_cost = mapped_column(Float)
    expected_net_return = mapped_column(Float)
    confidence = mapped_column(Float)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at = mapped_column(TS, nullable=False)
    __table_args__ = (
        CheckConstraint("direction IN ('buy','sell','none')", name="ck_signals_direction"),
        CheckConstraint("decision IN ('open','close','hold','skip')", name="ck_signals_decision"),
    )


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id = mapped_column(Integer, ForeignKey("signals.id"))
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    order_type: Mapped[str] = mapped_column(Text, nullable=False)
    requested_price = mapped_column(DEC)
    quantity = mapped_column(DEC, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_paper: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(TS, nullable=False)
    __table_args__ = (
        CheckConstraint("side IN ('buy','sell')", name="ck_orders_side"),
        CheckConstraint("order_type IN ('market','limit')", name="ck_orders_type"),
        CheckConstraint("is_paper = 1", name="ck_orders_paper"),
    )


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reason = mapped_column(Text)
    created_at = mapped_column(TS, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','partial','filled','cancelled','rejected','expired')",
            name="ck_order_events_status",
        ),
    )


class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    executed_price = mapped_column(DEC, nullable=False)
    executed_quantity = mapped_column(DEC, nullable=False)
    fx_rate_to_gbp = mapped_column(DEC, nullable=False)
    fees = mapped_column(DEC, nullable=False, server_default="0")
    slippage = mapped_column(DEC, nullable=False, server_default="0")
    liquidity_source = mapped_column(Text)
    executed_at = mapped_column(TS, nullable=False)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity = mapped_column(DEC, nullable=False)
    average_entry_price = mapped_column(DEC, nullable=False)
    current_value = mapped_column(DEC)
    realised_pnl = mapped_column(DEC, nullable=False, server_default="0")
    unrealised_pnl = mapped_column(DEC)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    exit_reason = mapped_column(Text)
    opened_at = mapped_column(TS, nullable=False)
    closed_at = mapped_column(TS)
    __table_args__ = (CheckConstraint("status IN ('open','closed','settled')", name="ck_positions_status"),)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp = mapped_column(TS, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    cash = mapped_column(DEC, nullable=False)
    positions_value = mapped_column(DEC, nullable=False)
    total_equity = mapped_column(DEC, nullable=False)
    exposure = mapped_column(DEC, nullable=False)
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    realised_pnl = mapped_column(DEC, nullable=False)
    unrealised_pnl = mapped_column(DEC, nullable=False)
    drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    __table_args__ = (CheckConstraint("mode IN ('live','backtest')", name="ck_snapshots_mode"),)


class Resolution(Base):
    __tablename__ = "resolutions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(Integer, ForeignKey("markets.id"), nullable=False, unique=True)
    resolved_at = mapped_column(TS, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    source = mapped_column(Text)
    retrieved_at = mapped_column(TS, nullable=False)
    raw_json = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('YES','NO','INVALID','SPLIT','CANCELLED')", name="ck_resolutions_outcome"
        ),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_id: Mapped[int] = mapped_column(Integer, ForeignKey("forecasts.id"), nullable=False)
    evaluated_at = mapped_column(TS, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    actual_observation_id = mapped_column(Integer, ForeignKey("observations.id"))
    error = mapped_column(Float)
    absolute_error = mapped_column(Float)
    squared_error = mapped_column(Float)
    direction_correct = mapped_column(Integer)
    pinball_loss = mapped_column(Float)
    crps = mapped_column(Float)
    in_80_interval = mapped_column(Integer)
    in_98_interval = mapped_column(Integer)
    evaluation_version: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("forecast_id", "evaluation_version"),)


class EvaluationSummary(Base):
    __tablename__ = "evaluation_summaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    computed_at = mapped_column(TS, nullable=False)
    evaluation_version: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    model_name = mapped_column(Text)
    model_size = mapped_column(Text)
    strategy_name = mapped_column(Text)
    asset_id = mapped_column(Integer)
    horizon = mapped_column(Integer)
    segment_json = mapped_column(Text)
    window_start = mapped_column(TS)
    window_end = mapped_column(TS)
    is_holdout: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    ci_low = mapped_column(Float)
    ci_high = mapped_column(Float)
    baseline_value = mapped_column(Float)
    p_value = mapped_column(Float)
    __table_args__ = (CheckConstraint("scope IN ('model','strategy')", name="ck_summaries_scope"),)


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(TS, nullable=False)
    asset_id = mapped_column(Integer)
    source = mapped_column(Text)
    check_name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    details_json = mapped_column(Text)
    __table_args__ = (CheckConstraint("severity IN ('info','warning','error')", name="ck_dq_severity"),)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for = mapped_column(Text)
    started_at = mapped_column(TS, nullable=False)
    finished_at = mapped_column(TS)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error = mapped_column(Text)
    stats_json = mapped_column(Text)
    __table_args__ = (UniqueConstraint("job_name", "scheduled_for"),)


class SystemState(Base):
    __tablename__ = "system_state"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at = mapped_column(TS, nullable=False)


IMMUTABLE_TABLES = ("forecasts", "signals", "orders", "fills")
