"""Download the four Timestral checkpoints into data/models/ and write data/models/manifest.json.

Idempotent and resumable (huggingface_hub skips complete files and resumes partial ones).
Each model directory keeps the repo's LICENSE and README (model card) next to the weights.

    uv run python scripts/download_models.py [--sizes 5M 28M] [--revision <sha>]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "models"
REPOS = {
    "5M": "mistralai/Timestral-5M",
    "28M": "mistralai/Timestral-28M",
    "123M": "mistralai/Timestral-123M",
    "209M": "mistralai/Timestral-209M",
}
EXPECTED_MB = {"5M": 20.8, "28M": 111, "123M": 490, "209M": 837}  # brief §3.1
PATTERNS = ["config.json", "model.safetensors", "LICENSE*", "README.md", "*.md"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="+", default=list(REPOS), choices=list(REPOS))
    ap.add_argument("--revision", default=None, help="pin a revision (default: current main)")
    args = ap.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MODEL_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"models": []}
    by_repo = {m["repo_id"]: m for m in manifest["models"]}
    api = HfApi()
    ok = True
    for size in args.sizes:
        repo = REPOS[size]
        info = api.model_info(repo, revision=args.revision, files_metadata=True)
        target = MODEL_DIR / repo.split("/")[1]
        print(f"[{size}] {repo} @ {info.sha[:12]} -> {target}")
        snapshot_download(repo, revision=info.sha, local_dir=target, allow_patterns=PATTERNS)
        files = {}
        for f in sorted(target.iterdir()):
            if f.is_file():
                files[f.name] = f.stat().st_size
        remote = {s.rfilename: s.size for s in info.siblings if s.rfilename in files}
        mismatched = [n for n, sz in remote.items() if sz is not None and files[n] != sz]
        weights_mb = files.get("model.safetensors", 0) / 1e6
        within = abs(weights_mb - EXPECTED_MB[size]) / EXPECTED_MB[size] <= 0.01
        has_license = any(n.upper().startswith("LICENSE") for n in files)
        print(
            f"    weights {weights_mb:.1f} MB (expected {EXPECTED_MB[size]} MB, within 1%: {within}); "
            f"licence file: {has_license}; size mismatches vs Hub: {mismatched or 'none'}"
        )
        ok &= within and has_license and not mismatched
        by_repo[repo] = {
            "size": size,
            "repo_id": repo,
            "revision": info.sha,
            "local_dir": str(target.relative_to(ROOT)),
            "files": files,
            "weights_mb": round(weights_mb, 2),
            "expected_mb": EXPECTED_MB[size],
            "within_1pct": within,
            "downloaded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    manifest["models"] = [by_repo[r] for r in REPOS.values() if r in by_repo]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {manifest_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
