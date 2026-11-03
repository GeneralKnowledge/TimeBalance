"""Load the configurable question set (config/decision_tasks.yaml)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from mpe.config import CONFIG_DIR
from mpe.decisions.base import DecisionQuestion

DEFAULT_TASKS = CONFIG_DIR / "decision_tasks.yaml"


def load_questions(path: Path | None = None) -> tuple[str, str, list[DecisionQuestion]]:
    """(version label, content hash, questions)."""
    data = yaml.safe_load((path or DEFAULT_TASKS).read_text())
    qs = [
        DecisionQuestion(
            id=q["id"],
            kind=q["kind"],
            prompt=q["prompt"],
            candidates=tuple(str(c) for c in q["candidates"]),
            descriptions=tuple(q.get("descriptions") or ()),
            positive=q.get("positive"),
            abstain_below=q.get("abstain_below"),
        )
        for q in data["questions"]
    ]
    if len({q.id for q in qs}) != len(qs):
        raise ValueError("duplicate question ids")
    digest = hashlib.sha256(json.dumps([q.to_dict() for q in qs], sort_keys=True).encode()).hexdigest()[:12]
    return str(data.get("version", "unversioned")), digest, qs
