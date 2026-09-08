"""Shard listesinin statik, config-dosyası tabanlı yüklenmesi.

CLAUDE.md'nin yasak listesi gereği shard ataması Raft/Paxos/etcd gibi
dinamik bir cluster coordination aracıyla değil, düz bir config dosyasıyla
tanımlanıyor. Faz 8'de gerçek per-shard depolamaya bağlanana kadar bu
liste sadece TutarliHash'i kurmak için kullanılıyor.
"""

import json
from pathlib import Path

_VARSAYILAN_CONFIG_YOLU = Path(__file__).resolve().parents[3] / "config" / "shards.json"


def shardlari_yukle(yol: str | Path = _VARSAYILAN_CONFIG_YOLU) -> list[str]:
    icerik = json.loads(Path(yol).read_text(encoding="utf-8"))
    return icerik["shardlar"]
