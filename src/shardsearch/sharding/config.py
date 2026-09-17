"""Static, config-file-based loading of the shard list.

Per SPEC.md's scope, shard assignment is defined by a plain config file
rather than a dynamic cluster coordination tool like Raft/Paxos/etcd.
This list is used only to build a ConsistentHash instance.
"""

import json
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "shards.json"


def load_shards(path: str | Path = _DEFAULT_CONFIG_PATH) -> list[str]:
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    return content["shards"]
