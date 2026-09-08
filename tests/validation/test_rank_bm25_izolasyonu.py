"""rank_bm25'in src/ içine sızmadığını otomatik doğrular.

CLAUDE.md'nin yasak listesi manuel disipline bırakılmasın diye: birisi
yanlışlıkla src/ içine `import rank_bm25` yazarsa bu test kırılır. AST
üzerinden gerçek import düğümlerini arıyoruz (düz metin araması değil) —
yoksa bu formül farkını açıklayan docstring'deki "rank_bm25" kelimesi
bile yanlış pozitife yol açar. Bu test rank_bm25'in kurulu olmasına
ihtiyaç duymaz, bu yüzden validation bağımlılık grubu kurulu olmasa bile
çalışır.
"""

import ast
from pathlib import Path

SRC_DIZINI = Path(__file__).resolve().parents[2] / "src"


def _rank_bm25_import_ediyor_mu(dosya: Path) -> bool:
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "rank_bm25" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "rank_bm25":
                return True
    return False


def test_rank_bm25_src_icine_sizmamis() -> None:
    ihlaller = [dosya for dosya in SRC_DIZINI.rglob("*.py") if _rank_bm25_import_ediyor_mu(dosya)]
    assert not ihlaller, f"rank_bm25 src/ içine import edilmiş: {ihlaller}"
