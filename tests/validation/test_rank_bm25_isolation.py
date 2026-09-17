"""Automatically verifies that rank_bm25 never leaks into src/.

This exists so the project's rule isn't left to manual discipline alone:
if someone accidentally writes `import rank_bm25` inside src/, this test
fails. Real import nodes are searched via the AST (not a plain text
search) — a text search would false-positive on the word "rank_bm25"
appearing in a docstring explaining this formula difference. This test
doesn't require rank_bm25 to be installed, so it runs even if the
validation dependency group isn't set up.
"""

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"


def _imports_rank_bm25(file: Path) -> bool:
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "rank_bm25" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "rank_bm25":
                return True
    return False


def test_rank_bm25_has_not_leaked_into_src() -> None:
    violations = [file for file in SRC_DIR.rglob("*.py") if _imports_rank_bm25(file)]
    assert not violations, f"rank_bm25 is imported inside src/: {violations}"
