"""The base unit of an inverted index: one token's record in one document."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Posting:
    doc_id: str
    frequency: int
    positions: list[int]
