"""Provider-independent decision-model interface.

A :class:`DecisionModel` answers structured questions about a text/JSON *state* (here a
point-in-time market snapshot) by distributing probability over predefined candidate answers.
It is deliberately separate from :class:`mpe.models.base.ForecastModel`: a decision model does
not forecast a numeric series, and nothing in the forecasting pipeline depends on this module.

Semantics that every adapter must respect:

* ``probabilities`` is what the model *reports*. It is not evidence of calibration; calibration
  is only ever measured empirically by :mod:`mpe.decisions.evaluate`.
* ``confidence`` is the model's own number (if any) and may mean different things per provider;
  ``confidence_kind`` names it.
* ``abstained`` is set when the model, or the experiment's abstention rule, declines to answer.
* ``raw`` keeps the provider's untouched output; normalised fields are derived from it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol, runtime_checkable

QuestionKind = Literal["binary", "choice", "ordinal"]


class DecisionModelError(RuntimeError):
    """The model failed to produce an answer (load failure, inference error, malformed output)."""


@dataclass(frozen=True)
class DecisionModelMetadata:
    name: str  # 'laya-typed-decisions'
    provider: str  # 'laya'
    checkpoint: str  # 'convaiinnovations/laya:typed-decisions'
    version: str  # resolved HF commit SHA, package version, ...
    library_version: str | None
    supported_kinds: tuple[str, ...]
    reports_probabilities: bool
    reports_confidence: bool
    max_input_tokens: int | None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DecisionQuestion:
    """One structured question with predefined candidate answers.

    ``binary`` questions have exactly two candidates and ``positive`` names the one whose
    probability is the question's headline number (e.g. ``"yes"`` for P(resolves YES)).
    ``ordinal`` candidates are ordered from lowest to highest.
    """

    id: str
    kind: QuestionKind
    prompt: str
    candidates: tuple[str, ...]
    descriptions: tuple[str, ...] = ()  # optional per-candidate text the model sees
    positive: str | None = None
    abstain_below: float | None = None  # experiment rule: abstain when model confidence < this

    def __post_init__(self) -> None:
        if not self.id or not self.prompt:
            raise ValueError("question needs an id and a prompt")
        if len(self.candidates) < 2 or len(set(self.candidates)) != len(self.candidates):
            raise ValueError(f"question {self.id!r}: need >= 2 distinct candidates")
        if self.descriptions and len(self.descriptions) != len(self.candidates):
            raise ValueError(f"question {self.id!r}: descriptions must match candidates")
        if self.kind == "binary" and (len(self.candidates) != 2 or self.positive not in self.candidates):
            raise ValueError(f"question {self.id!r}: binary needs 2 candidates and a positive one")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DecisionRequest:
    request_id: str  # stable id of (snapshot, question set)
    state: dict  # the rendered, point-in-time input; JSON-serialisable
    questions: Sequence[DecisionQuestion]
    decision_ts: str  # ISO UTC information cutoff of ``state``
    input_schema: str  # e.g. 'polymarket-snapshot/v1'


@dataclass(frozen=True)
class DecisionAnswer:
    question_id: str
    kind: str
    probabilities: dict[str, float] | None  # candidate -> probability (sums to ~1)
    choice: str | None  # argmax candidate, None if abstained/failed
    positive_probability: float | None  # binary only
    expected_level: float | None  # ordinal only: E[index], 0..k-1
    confidence: float | None
    confidence_kind: str | None  # what ``confidence`` means for this provider
    abstained: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DecisionResult:
    request_id: str
    model: DecisionModelMetadata
    answers: dict[str, DecisionAnswer]
    raw: dict | None  # provider output, untouched (JSON-serialisable)
    latency_ms: float
    device: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class DecisionModel(Protocol):
    def load(self, device: str = "auto") -> None: ...
    def unload(self) -> None: ...
    def metadata(self) -> DecisionModelMetadata: ...
    def decide_batch(self, requests: Sequence[DecisionRequest]) -> list[DecisionResult]: ...
    @property
    def is_loaded(self) -> bool: ...


def failed_answers(questions: Sequence[DecisionQuestion], error: str) -> dict[str, DecisionAnswer]:
    return {
        q.id: DecisionAnswer(q.id, q.kind, None, None, None, None, None, None, abstained=True, error=error)
        for q in questions
    }


def normalise_distribution(question: DecisionQuestion, probs: dict[str, float]) -> dict[str, float]:
    """Validate a candidate distribution and renormalise it; raise DecisionModelError if unusable."""
    missing = [c for c in question.candidates if c not in probs]
    if missing:
        raise DecisionModelError(f"{question.id}: output lacks candidates {missing}")
    vals = [float(probs[c]) for c in question.candidates]
    if any(math.isnan(v) or v < 0 for v in vals):
        raise DecisionModelError(f"{question.id}: invalid probabilities {vals}")
    s = sum(vals)
    if s <= 0:
        raise DecisionModelError(f"{question.id}: probabilities sum to {s}")
    return {c: v / s for c, v in zip(question.candidates, vals, strict=True)}


def answer_from_distribution(
    question: DecisionQuestion, probs: dict[str, float], confidence: float | None, confidence_kind: str | None
) -> DecisionAnswer:
    p = normalise_distribution(question, probs)
    abstain = (
        question.abstain_below is not None and confidence is not None and confidence < question.abstain_below
    )
    choice = max(question.candidates, key=lambda c: p[c])
    return DecisionAnswer(
        question_id=question.id,
        kind=question.kind,
        probabilities=p,
        choice=None if abstain else choice,
        positive_probability=p[question.positive] if question.kind == "binary" else None,
        expected_level=(
            sum(i * p[c] for i, c in enumerate(question.candidates)) if question.kind == "ordinal" else None
        ),
        confidence=confidence,
        confidence_kind=confidence_kind,
        abstained=abstain,
    )
