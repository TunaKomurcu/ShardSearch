"""Ters indeksin temel birimi: bir token'ın tek bir belgedeki kaydı."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Posting:
    belge_id: str
    frekans: int
    pozisyonlar: list[int]
