"""Sorgu ayrıştırma ağacının düğümleri.

Ortak bir taban sınıf tanımlanmadı — dört düğüm türü de birbirinden
bağımsız `dataclass`'lar, `degerlendirici.py`'de `isinstance` ile ayırt
ediliyor. Dört düğüm için soyutlama gerektirecek ortak bir davranış yok.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Terim:
    kelime: str


@dataclass(frozen=True)
class Ifade:
    kelimeler: tuple[str, ...]


@dataclass(frozen=True)
class Ve:
    sol: "SorguDugumu"
    sag: "SorguDugumu"


@dataclass(frozen=True)
class Veya:
    sol: "SorguDugumu"
    sag: "SorguDugumu"


SorguDugumu = Terim | Ifade | Ve | Veya
