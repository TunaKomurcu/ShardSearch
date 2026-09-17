"""Automatically verifies that fakeredis never leaks into src/.

The same discipline as tests/validation/test_rank_bm25_isolation.py for
rank_bm25: fakeredis is a test library, standing in for real Redis ONLY
in tests (see the monkeypatch in tests/unit/test_api.py). It must never
enter `src/` — production code should always use real `redis.Redis`. Real
import nodes are searched via the AST (not a plain text search), so this
test doesn't require fakeredis to be installed.
"""

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"


def _imports_fakeredis(file: Path) -> bool:
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "fakeredis" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "fakeredis":
                return True
    return False


def test_fakeredis_has_not_leaked_into_src() -> None:
    violations = [file for file in SRC_DIR.rglob("*.py") if _imports_fakeredis(file)]
    assert not violations, f"fakeredis is imported inside src/: {violations}"
