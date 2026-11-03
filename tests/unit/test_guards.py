"""Cross-cutting guard tests (brief §11)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_DIRS = [ROOT / "src", ROOT / "scripts"]
FORBIDDEN_MODULES = {
    "py_clob_client", "ccxt", "alpaca", "alpaca_trade_api", "ib_insync", "ibapi", "web3", "eth_account",
    "binance", "coinbase", "kraken", "robin_stocks", "tradier", "oandapyV20", "MetaTrader5",
}  # fmt: skip
FORBIDDEN_STRINGS = ("/order", "post_order", "create_order", "place_order", "private_key", "api_secret")


def _py_files():
    for d in CODE_DIRS:
        yield from d.rglob("*.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    return mods


def test_timestral_isolated():
    allowed = ROOT / "src" / "mpe" / "models" / "timestral.py"
    offenders = [p for p in _py_files() if "timestral" in _imports(p) and p != allowed]
    assert not offenders, f"only {allowed} may import timestral: {offenders}"


def test_no_real_trading_clients():
    for p in _py_files():
        bad = _imports(p) & FORBIDDEN_MODULES
        assert not bad, f"{p} imports trading/wallet libraries {bad}"
        if p.name == "test_guards.py":
            continue
        text = p.read_text().lower()
        for s in FORBIDDEN_STRINGS:
            assert s not in text, f"{p} references {s!r}"
