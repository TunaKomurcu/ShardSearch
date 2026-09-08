"""Faz 0 doğrulaması: proje iskeleti kurulu ve pytest çalışıyor.

Gerçek testler Faz 1'den itibaren gelecek (tokenizer, ters indeks, vb.).
"""

import shardsearch


def test_paket_import_edilebiliyor() -> None:
    assert shardsearch is not None
