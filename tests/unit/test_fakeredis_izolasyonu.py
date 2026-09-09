"""fakeredis'in src/ içine sızmadığını otomatik doğrular.

rank_bm25 için tests/validation/test_rank_bm25_izolasyonu.py'de kurduğumuz
aynı disiplin: fakeredis bir test kütüphanesi, gerçek Redis'in yerini
tutması SADECE testlerde (bkz. tests/unit/test_api.py'deki monkeypatch).
`src/`'ye asla girmemeli — üretim kodu her zaman gerçek `redis.Redis`
kullanmalı. AST üzerinden gerçek import düğümlerini arıyoruz (düz metin
araması değil), bu test fakeredis'in kurulu olmasına ihtiyaç duymaz.
"""

import ast
from pathlib import Path

SRC_DIZINI = Path(__file__).resolve().parents[2] / "src"


def _fakeredis_import_ediyor_mu(dosya: Path) -> bool:
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "fakeredis" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "fakeredis":
                return True
    return False


def test_fakeredis_src_icine_sizmamis() -> None:
    ihlaller = [dosya for dosya in SRC_DIZINI.rglob("*.py") if _fakeredis_import_ediyor_mu(dosya)]
    assert not ihlaller, f"fakeredis src/ içine import edilmiş: {ihlaller}"
