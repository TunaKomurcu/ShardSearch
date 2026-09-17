"""Persistent, SQLite-backed version of the inverted index.

Exposes the EXACT SAME method surface as InvertedIndex (add_document,
get_postings, document_count, document_length, average_document_length,
document_text) — the only difference is the data lives on disk in three
tables instead of in an in-memory dict. No formal Protocol/ABC is
defined; duck-typing is enough for now.

Schema:
- documents(doc_id PK, length, text): each document's token count and
  original text (the text is kept so /search results can display it).
- postings(token, doc_id, frequency, positions), PK(token, doc_id): this
  primary key also forms an index ordered by (token, doc_id), so
  "WHERE token=? ORDER BY doc_id" comes back already sorted via an index
  scan with no extra sort step — the SQLite counterpart of the in-memory
  version's bisect-based insertion order.
- meta(id=0 single row, total_document_count, total_document_length):
  without this, document_count()/average_document_length() would have to
  COUNT(*)/SUM(length) over the whole documents table on every call — the
  exact O(n) computation we deliberately avoided when designing BM25.
  Instead this single row is updated incrementally, in the same
  transaction, on every add_document/upsert, so reads stay O(1).

Thread-safety (added for the FastAPI integration): `check_same_thread=False`
ONLY disables Python's "this connection may not be used outside the
thread that created it" check — the SQLite connection itself is still not
safe for concurrent multi-threaded access. FastAPI runs synchronous
(`def`) routes in a thread pool via Starlette, so the single
SqliteInvertedIndex connection shared by the API can genuinely be
accessed from different threads. `self._lock` (a `threading.Lock`) wraps
every method that touches the connection, enforcing SQLite's implicit
"one user at a time" assumption on the code side — the smallest correct
fix for this scope, short of building a real connection pool.
"""

import json
import sqlite3
import threading
from pathlib import Path

from shardsearch.index.postings import Posting
from shardsearch.tokenizer import tokenize

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    length INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    token TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    frequency INTEGER NOT NULL,
    positions TEXT NOT NULL,
    PRIMARY KEY (token, doc_id)
);

-- The (token, doc_id) primary key is only efficient for searches that
-- start with token (WHERE token=?) — an index can be used when the
-- search matches a sorted prefix of its columns FROM THE LEFT. Searching
-- by doc_id ALONE (to delete "all postings for this document" during an
-- upsert) can't use that composite index, so SQLite would have to scan
-- the whole postings table. Hence a separate index on doc_id — the
-- SQLite counterpart of the in-memory version's _document_tokens map
-- (there a Python dict, here a SQLite index, same purpose).
CREATE INDEX IF NOT EXISTS idx_postings_doc_id ON postings (doc_id);

CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 0),
    total_document_count INTEGER NOT NULL,
    total_document_length INTEGER NOT NULL
);
"""


class SqliteInvertedIndex:
    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta (id, total_document_count, total_document_length) "
                "VALUES (0, 0, 0)"
            )
            self._conn.commit()

    def add_document(self, doc_id: str, text: str) -> None:
        with self._lock, self._conn:
            exists = self._conn.execute(
                "SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            if exists is not None:
                self._remove_document(doc_id)

            tokens = tokenize(text)
            positions_by_token: dict[str, list[int]] = {}
            for position, token in enumerate(tokens):
                positions_by_token.setdefault(token, []).append(position)

            self._conn.execute(
                "INSERT INTO documents (doc_id, length, text) VALUES (?, ?, ?)",
                (doc_id, len(tokens), text),
            )
            self._conn.executemany(
                "INSERT INTO postings (token, doc_id, frequency, positions) "
                "VALUES (?, ?, ?, ?)",
                [
                    (token, doc_id, len(positions), json.dumps(positions))
                    for token, positions in positions_by_token.items()
                ],
            )
            self._update_meta(count_delta=1, length_delta=len(tokens))

    def _remove_document(self, doc_id: str) -> None:
        # The caller (add_document) already holds self._lock — we don't
        # lock again here (re-acquiring a threading.Lock on the same
        # thread would deadlock forever).
        old_length = self._conn.execute(
            "SELECT length FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()[0]
        self._conn.execute("DELETE FROM postings WHERE doc_id = ?", (doc_id,))
        self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._update_meta(count_delta=-1, length_delta=-old_length)

    def _update_meta(self, count_delta: int, length_delta: int) -> None:
        self._conn.execute(
            "UPDATE meta SET total_document_count = total_document_count + ?, "
            "total_document_length = total_document_length + ? WHERE id = 0",
            (count_delta, length_delta),
        )

    def get_postings(self, token: str) -> list[Posting]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT doc_id, frequency, positions FROM postings "
                "WHERE token = ? ORDER BY doc_id",
                (token,),
            ).fetchall()
        return [
            Posting(doc_id, frequency, json.loads(positions))
            for doc_id, frequency, positions in rows
        ]

    def document_count(self) -> int:
        with self._lock:
            (value,) = self._conn.execute(
                "SELECT total_document_count FROM meta WHERE id = 0"
            ).fetchone()
        return value

    def document_length(self, doc_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT length FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        if row is None:
            raise KeyError(doc_id)
        return row[0]

    def document_text(self, doc_id: str) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT text FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        if row is None:
            raise KeyError(doc_id)
        return row[0]

    def average_document_length(self) -> float:
        with self._lock:
            count, length = self._conn.execute(
                "SELECT total_document_count, total_document_length FROM meta WHERE id = 0"
            ).fetchone()
        if count == 0:
            return 0.0
        return length / count

    def close(self) -> None:
        self._conn.close()
