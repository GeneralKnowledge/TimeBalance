"""CLI entry point `mpe`. M0 only lists the registered models."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from mpe.models.registry import REGISTRY

    args = sys.argv[1:] if argv is None else argv
    if args[:2] == ["models", "list"]:
        for name in sorted(REGISTRY):
            print(name)
        return 0
    print("usage: mpe models list   (more commands arrive in M1+)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
