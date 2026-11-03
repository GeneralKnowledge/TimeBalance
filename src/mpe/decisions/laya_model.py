"""Laya adapter (https://github.com/NandhaKishorM/laya, weights convaiinnovations/laya).

Laya is a non-generative ModernBERT classifier: one forward pass scores predefined options for
each question. Verified against laya 0.4.22's source (``laya.agent.Agent``):

* ``laya.load(repo, subfolder=..., device=..., revision=...)`` returns an ``Agent``;
  ``agent.revision`` is the resolved Hub commit.
* ``agent.predict_batch(states, questions, batch_size=...)`` returns one ``{"answers": {...}}``
  per state. Question types: ``choice`` (criteria dict label -> description), ``score`` (ordinal
  list) and ``noul`` (P(true)).
* Each answer carries ``probabilities`` (choice/score), ``noul`` (noul), ``confidence`` and
  ``answer_confidence``. Its model card says the shipped probabilities are over-confident and
  that ``noul`` can follow its label wording, so binary questions are asked as two-option
  ``choice`` questions by default (the card's own workaround).

``laya`` and ``torch`` are imported lazily so the rest of TimeBalance never needs them.
"""

from __future__ import annotations

import gc
import time
from collections.abc import Sequence
from importlib import metadata as importlib_metadata

from mpe.decisions.base import (
    DecisionAnswer,
    DecisionModelError,
    DecisionModelMetadata,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    answer_from_distribution,
    failed_answers,
)

DEFAULT_REPO = "convaiinnovations/laya"
CHECKPOINTS = {"typed-decisions": "typed-decisions", "english": None, "multilingual": "multilingual"}
CONFIDENCE_KIND = "laya.answer_confidence (model-reported, uncalibrated for this domain)"


def to_laya_question(q: DecisionQuestion, binary_as: str = "choice") -> dict:
    desc = q.descriptions or q.candidates
    if q.kind == "ordinal":
        return {"type": "score", "instructions": q.prompt, "criteria": list(desc)}
    if q.kind == "binary" and binary_as == "noul":
        return {"type": "noul", "instructions": q.prompt}
    return {"type": "choice", "instructions": q.prompt,
            "criteria": dict(zip(q.candidates, desc, strict=True))}  # fmt: skip


def from_laya_answer(q: DecisionQuestion, raw: dict, binary_as: str = "choice") -> DecisionAnswer:
    if not isinstance(raw, dict):
        raise DecisionModelError(f"{q.id}: missing answer")
    conf = raw.get("answer_confidence", raw.get("confidence"))
    conf = None if conf is None else float(conf)
    t = raw.get("type")
    if q.kind == "binary" and binary_as == "noul":
        if t != "noul" or raw.get("noul") is None:
            raise DecisionModelError(f"{q.id}: expected a noul answer, got {t!r}")
        p = float(raw["noul"])
        neg = next(c for c in q.candidates if c != q.positive)
        probs = {q.positive: p, neg: 1.0 - p}
    elif q.kind == "ordinal":
        if t != "score" or not isinstance(raw.get("probabilities"), dict):
            raise DecisionModelError(f"{q.id}: expected a score answer, got {t!r}")
        rp = raw["probabilities"]
        probs = {c: float(rp.get(str(i), float("nan"))) for i, c in enumerate(q.candidates)}
    else:
        if t != "choice" or not isinstance(raw.get("probabilities"), dict):
            raise DecisionModelError(f"{q.id}: expected a choice answer, got {t!r}")
        probs = {str(k): float(v) for k, v in raw["probabilities"].items()}
    return answer_from_distribution(q, probs, conf, CONFIDENCE_KIND)


class LayaDecisionModel:
    """:class:`mpe.decisions.base.DecisionModel` backed by a Laya checkpoint."""

    def __init__(
        self,
        checkpoint: str = "typed-decisions",
        repo: str = DEFAULT_REPO,
        revision: str | None = None,
        binary_as: str = "choice",
        batch_size: int = 8,
        agent=None,  # tests inject a fake agent
    ) -> None:
        if checkpoint not in CHECKPOINTS:
            raise ValueError(f"unknown Laya checkpoint {checkpoint!r}; known: {sorted(CHECKPOINTS)}")
        if binary_as not in ("choice", "noul"):
            raise ValueError("binary_as must be 'choice' or 'noul'")
        self.checkpoint = checkpoint
        self.repo = repo
        self.requested_revision = revision
        self.binary_as = binary_as
        self.batch_size = batch_size
        self._agent = agent
        self._device = "cpu"
        self.load_seconds: float | None = None

    # ------------------------------------------------------------------ lifecycle
    @property
    def is_loaded(self) -> bool:
        return self._agent is not None

    def load(self, device: str = "auto") -> None:
        if self._agent is not None:
            return
        import laya  # lazy

        t0 = time.perf_counter()
        try:
            self._agent = laya.load(
                self.repo, subfolder=CHECKPOINTS[self.checkpoint], revision=self.requested_revision,
                device=None if device == "auto" else device,
            )  # fmt: skip
        except Exception as e:
            raise DecisionModelError(f"Laya load failed: {type(e).__name__}: {e}") from e
        self.load_seconds = time.perf_counter() - t0
        self._device = str(getattr(self._agent, "device", "cpu"))

    def unload(self) -> None:
        self._agent = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def metadata(self) -> DecisionModelMetadata:
        try:
            lib = importlib_metadata.version("laya")
        except importlib_metadata.PackageNotFoundError:
            lib = None
        rev = getattr(self._agent, "revision", None) or self.requested_revision or "unresolved"
        sub = CHECKPOINTS[self.checkpoint]
        return DecisionModelMetadata(
            name=f"laya-{self.checkpoint}", provider="laya",
            checkpoint=f"{self.repo}:{sub or '.'}", version=str(rev), library_version=lib,
            supported_kinds=("binary", "choice", "ordinal"), reports_probabilities=True,
            reports_confidence=True, max_input_tokens=1024 if self.checkpoint == "typed-decisions" else 512,
            extra={"binary_as": self.binary_as, "batch_size": self.batch_size, "device": self._device},
        )  # fmt: skip

    # ------------------------------------------------------------------ inference
    def decide_batch(self, requests: Sequence[DecisionRequest]) -> list[DecisionResult]:
        if not requests:
            return []
        if self._agent is None:
            raise DecisionModelError("Laya model is not loaded")
        meta = self.metadata()
        # predict_batch takes one question set for all states; group requests that share one.
        groups: dict[tuple, list[int]] = {}
        for i, r in enumerate(requests):
            groups.setdefault(tuple(q.id for q in r.questions), []).append(i)
        out: list[DecisionResult | None] = [None] * len(requests)
        for idxs in groups.values():
            questions = requests[idxs[0]].questions
            lq = {q.id: to_laya_question(q, self.binary_as) for q in questions}
            for start in range(0, len(idxs), self.batch_size):
                chunk = idxs[start : start + self.batch_size]
                t0 = time.perf_counter()
                try:
                    raws = self._agent.predict_batch([requests[i].state for i in chunk], lq,
                                                     batch_size=self.batch_size)  # fmt: skip
                    err = None
                    if not isinstance(raws, list) or len(raws) != len(chunk):
                        raise DecisionModelError("predict_batch returned the wrong number of results")
                except Exception as e:  # noqa: BLE001 - record, never crash the experiment
                    raws, err = [None] * len(chunk), f"{type(e).__name__}: {e}"
                per = (time.perf_counter() - t0) * 1000 / len(chunk)
                for i, raw in zip(chunk, raws, strict=True):
                    out[i] = self._result(requests[i], meta, raw, per, err)
        return [r for r in out if r is not None]

    def _result(self, req: DecisionRequest, meta, raw, latency_ms: float, err: str | None) -> DecisionResult:
        if err is not None:
            return DecisionResult(req.request_id, meta, failed_answers(req.questions, err), None,
                                  latency_ms, self._device, err)  # fmt: skip
        answers: dict[str, DecisionAnswer] = {}
        errors = []
        raw_answers = (raw or {}).get("answers", {}) if isinstance(raw, dict) else {}
        for q in req.questions:
            try:
                answers[q.id] = from_laya_answer(q, raw_answers.get(q.id), self.binary_as)
            except DecisionModelError as e:
                errors.append(str(e))
                answers.update(failed_answers([q], str(e)))
        return DecisionResult(req.request_id, meta, answers, _jsonable(raw), latency_ms, self._device,
                              "; ".join(errors) or None)  # fmt: skip


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    try:
        return float(x)
    except (TypeError, ValueError):
        return str(x)
