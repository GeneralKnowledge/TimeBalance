"""Typed experiment configuration.

Every field that can change a forecast or a score is explicit in the saved configuration; nothing
depends on an undocumented default at run time. The experiment identity is a hash of the
canonical JSON of every field except ``name`` and ``notes``, so two configurations that would
produce different results can never share an id (and the same configuration always maps to the
same id, which is what makes re-running safe).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mpe.models.base import DEFAULT_QUANTILE_LEVELS
from mpe.storage.replay import KnowledgeMode

CONFIG_VERSION = "m2.1"

TIMESTRAL_MODELS = ("timestral-5m", "timestral-28m", "timestral-123m", "timestral-209m")
BASELINE_MODELS = ("zero", "persistence", "moving_average", "momentum", "linear_trend")
KNOWN_MODELS = TIMESTRAL_MODELS + BASELINE_MODELS

# Constructor parameters written into every saved configuration. They equal the M0 class defaults
# (mpe.models.baselines / mpe.models.timestral) but are recorded so a saved experiment does not
# depend on those defaults staying the same.
DEFAULT_MODEL_PARAMS: dict[str, dict[str, Any]] = {
    **{m: {"symmetric_averaging": True, "clip_nonnegative": False} for m in TIMESTRAL_MODELS},
    "zero": {"n_origins": 250, "max_context": 4096},
    "persistence": {"n_origins": 250, "max_context": 4096},
    "moving_average": {"window": 20, "n_origins": 250, "max_context": 4096},
    "momentum": {"lookback": 20, "n_origins": 250, "max_context": 4096},
    "linear_trend": {"window": 60, "n_origins": 250, "max_context": 4096},
}

Domain = Literal["stocks", "polymarket"]


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in KNOWN_MODELS:
            raise ValueError(f"unknown model {v!r}; known: {list(KNOWN_MODELS)}")
        return v

    @model_validator(mode="after")
    def _params(self):
        allowed = set(DEFAULT_MODEL_PARAMS[self.name])
        bad = set(self.params) - allowed
        if bad:
            raise ValueError(f"{self.name}: unknown parameters {sorted(bad)}; allowed {sorted(allowed)}")
        missing = allowed - set(self.params)
        if missing:
            raise ValueError(f"{self.name}: parameters must be explicit, missing {sorted(missing)}")
        return self

    @property
    def family(self) -> str:
        return "timestral" if self.name.startswith("timestral-") else "baseline"


def model_spec(name: str, **overrides: Any) -> ModelSpec:
    if name not in DEFAULT_MODEL_PARAMS:
        raise ValueError(f"unknown model {name!r}; known: {list(KNOWN_MODELS)}")
    return ModelSpec(name=name, params={**DEFAULT_MODEL_PARAMS[name], **overrides})


class Exclusion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset: str
    reason: str


def _utc(v: Any) -> Any:
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    if isinstance(v, datetime):
        if v.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware UTC")
        return v.astimezone(UTC)
    return v


class ExperimentConfig(BaseModel):
    """One walk-forward experiment. See docs/M2_RESEARCH_METHODOLOGY.md for field semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_version: Literal["m2.1"] = CONFIG_VERSION
    name: str
    notes: str = ""
    domain: Domain
    knowledge_mode: KnowledgeMode  # no default: every experiment states its replay mode
    # data selection
    source: str  # stored observation source, e.g. 'yfinance', 'polymarket_clob_history'
    interval: Literal["1d", "1h"]
    calendar: str | None  # exchange calendar for stocks (XNYS); None for hourly Polymarket
    assets: list[str]  # stock symbols, or Polymarket condition ids (YES token is used)
    outcome_side: Literal["YES"] | None  # Polymarket token side; YES is the only supported target
    price_field: Literal["close", "adj_close"]
    excluded_assets: list[Exclusion] = Field(default_factory=list)
    availability: dict[str, Any]  # replay rules and delays copied in at creation (provenance)
    # target
    target: Literal["log_return", "logit_price"]
    logit_eps: float | None
    respect_closing_time: bool  # Polymarket: no origin or target after the scheduled close
    # walk-forward design
    origin_start: datetime
    origin_end: datetime
    origin_stride: int  # in sessions (stocks) or hours (Polymarket)
    cutoff_delay_seconds: int  # cutoff = origin timestamp + this
    extra_latency_seconds: int  # reconstructed replay only: pessimistic extra delay
    targets_as_of: datetime  # knowledge time at which realised targets are read
    context_length: int  # target-series points given to every model
    min_context_observations: int
    max_missing_context_fraction: float
    horizons: list[int]  # steps (sessions / hours) ahead; one forecast path covers all
    quantile_levels: list[float]
    interval_levels: list[float]  # nominal central-interval coverages to report
    # models
    models: list[ModelSpec]
    reference_baseline: str  # the naive benchmark relative improvements are measured against
    seed: int
    device: Literal["auto", "cpu", "cuda"]
    # evaluation
    bootstrap_samples: int
    min_paired_dates: int  # fewer distinct origin dates than this = "insufficient data"

    @field_validator("origin_start", "origin_end", "targets_as_of", mode="before")
    @classmethod
    def _tz(cls, v: Any) -> Any:
        return _utc(v)

    @field_validator("horizons")
    @classmethod
    def _horizons(cls, v: list[int]) -> list[int]:
        if not v or any(int(h) < 1 for h in v):
            raise ValueError("horizons must be positive integers")
        if len(set(v)) != len(v):
            raise ValueError("horizons must be unique")
        if max(v) > 1024:
            raise ValueError("horizons above 1024 are not supported (one decode block)")
        return sorted(int(h) for h in v)

    @field_validator("quantile_levels")
    @classmethod
    def _levels(cls, v: list[float]) -> list[float]:
        if not v or any(not 0 < q < 1 for q in v) or sorted(set(v)) != list(v):
            raise ValueError("quantile_levels must be strictly increasing and inside (0, 1)")
        if 0.5 not in v:
            raise ValueError("quantile_levels must include 0.5 (the point forecast is the median)")
        return [float(q) for q in v]

    @model_validator(mode="after")
    def _consistent(self):
        if self.origin_end <= self.origin_start:
            raise ValueError("origin_end must be after origin_start")
        if self.origin_stride < 1:
            raise ValueError("origin_stride must be >= 1")
        if self.context_length < 2 or self.min_context_observations < 2:
            raise ValueError("context_length and min_context_observations must be >= 2")
        if self.min_context_observations > self.context_length:
            raise ValueError("min_context_observations cannot exceed context_length")
        if not 0 <= self.max_missing_context_fraction < 1:
            raise ValueError("max_missing_context_fraction must be in [0, 1)")
        if self.cutoff_delay_seconds < 0 or self.extra_latency_seconds < 0:
            raise ValueError("delays must not be negative")
        if self.knowledge_mode == KnowledgeMode.STRICT and self.extra_latency_seconds:
            raise ValueError("extra_latency_seconds applies to reconstructed replay only")
        if not self.assets:
            raise ValueError("no assets selected")
        if len(set(self.assets)) != len(self.assets):
            raise ValueError("assets must be unique")
        names = [m.name for m in self.models]
        if not names or len(set(names)) != len(names):
            raise ValueError("models must be a non-empty list without duplicates")
        if self.reference_baseline not in names:
            raise ValueError(f"reference_baseline {self.reference_baseline!r} must be one of the models")
        lo, hi = min(self.quantile_levels), max(self.quantile_levels)
        for c in self.interval_levels:
            a, b = round((1 - c) / 2, 10), round((1 + c) / 2, 10)
            if not 0 < c < 1 or a not in self.quantile_levels or b not in self.quantile_levels:
                raise ValueError(f"interval level {c} needs quantile levels {a} and {b}")
        if lo < 0.01 or hi > 0.99:
            raise ValueError("quantile levels outside [0.01, 0.99] would need extrapolation")
        if self.domain == "stocks":
            if self.interval != "1d" or self.calendar is None or self.target != "log_return":
                raise ValueError("stocks experiments use 1d bars, an exchange calendar and log returns")
            if self.outcome_side is not None or self.logit_eps is not None:
                raise ValueError("outcome_side / logit_eps are Polymarket settings")
        else:
            if self.interval != "1h" or self.calendar is not None or self.target != "logit_price":
                raise ValueError("Polymarket experiments use 1h samples and logit YES prices")
            if self.outcome_side != "YES":
                raise ValueError("Polymarket target must be the YES token price")
            if self.logit_eps is None or not 0 < self.logit_eps < 0.5:
                raise ValueError("logit_eps must be set in (0, 0.5)")
            if self.price_field != "close":
                raise ValueError("Polymarket samples are stored in 'close'")
        if self.targets_as_of < self.origin_end:
            raise ValueError("targets_as_of must not be before origin_end")
        return self

    # -- identity --------------------------------------------------------------------
    def identity_payload(self) -> dict:
        d = self.model_dump(mode="json")
        d.pop("name")
        d.pop("notes")
        return d

    def config_hash(self) -> str:
        blob = json.dumps(self.identity_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    @property
    def experiment_id(self) -> str:
        return f"{self.domain}-{self.config_hash()[:12]}"

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> ExperimentConfig:
        return cls.model_validate_json(text)

    @property
    def max_horizon(self) -> int:
        return max(self.horizons)

    @property
    def model_names(self) -> list[str]:
        return [m.name for m in self.models]


def availability_snapshot(settings, domain: Domain) -> dict[str, Any]:
    """The replay rules and configured delays an experiment depends on, copied into its config."""
    from mpe.storage.replay import AVAILABILITY_RULES

    src = ("yfinance", "1d") if domain == "stocks" else ("polymarket_clob_history", "1h")
    rule = AVAILABILITY_RULES[src]
    av = settings.availability
    out: dict[str, Any] = {"rule": rule.description, "source": src[0], "interval": src[1]}
    if domain == "stocks":
        out["stock_close_delay_minutes"] = av.stock_close_delay_minutes
    else:
        out["polymarket_history_latency_seconds"] = av.polymarket_history_latency_seconds
    return out


def default_config(
    domain: Domain,
    *,
    name: str,
    knowledge_mode: KnowledgeMode | str,
    assets: list[str],
    settings,
    origin_start: datetime,
    origin_end: datetime,
    targets_as_of: datetime | None = None,
    models: list[str | ModelSpec] | None = None,
    **overrides: Any,
) -> ExperimentConfig:
    """A complete configuration with the M2 defaults written out explicitly."""
    models = list(models or KNOWN_MODELS)
    if domain == "stocks":
        base: dict[str, Any] = dict(  # noqa: C408
            source="yfinance", interval="1d", calendar=settings.stocks.calendar, outcome_side=None,
            price_field="close", target="log_return", logit_eps=None, respect_closing_time=False,
            origin_stride=5, cutoff_delay_seconds=settings.availability.stock_close_delay_minutes * 60,
            context_length=512, min_context_observations=480, max_missing_context_fraction=0.05,
            horizons=[1, 5, 20], reference_baseline="zero",
        )  # fmt: skip
    else:
        base = dict(  # noqa: C408
            source="polymarket_clob_history", interval="1h", calendar=None, outcome_side="YES",
            price_field="close", target="logit_price", logit_eps=1e-4, respect_closing_time=True,
            origin_stride=6, cutoff_delay_seconds=300,
            context_length=336, min_context_observations=168, max_missing_context_fraction=0.25,
            horizons=[1, 6, 24], reference_baseline="persistence",
        )  # fmt: skip
    base.update(
        name=name, domain=domain, knowledge_mode=KnowledgeMode(knowledge_mode), assets=list(assets),
        availability=availability_snapshot(settings, domain), origin_start=origin_start,
        origin_end=origin_end, extra_latency_seconds=0,
        targets_as_of=targets_as_of or (origin_end + timedelta(days=45 if domain == "stocks" else 3)),
        quantile_levels=list(DEFAULT_QUANTILE_LEVELS), interval_levels=[0.5, 0.8, 0.9, 0.98],
        models=[m if isinstance(m, ModelSpec) else model_spec(m) for m in models], seed=0, device="auto",
        bootstrap_samples=2000, min_paired_dates=30,
    )  # fmt: skip
    base.update(overrides)
    return ExperimentConfig.model_validate(base)
