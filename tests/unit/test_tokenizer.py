"""Faz 1 testleri: tokenize() beklenen token listesini üretiyor mu.

Beklenen değerler elle hesaplandı (bkz. Faz 1 planı): önce turkish_lower,
sonra apostroftan öncesini alma, sonra sadece harfleri tutma kuralı.
"""

import pytest

from shardsearch.tokenizer import tokenize, turkish_lower


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        # 10 farklı Türkçe cümle
        ("Türkiye'nin başkenti Ankara'dır.", ["türkiye", "başkenti", "ankara"]),
        ("İstanbul çok güzel bir şehir!", ["istanbul", "çok", "güzel", "bir", "şehir"]),
        ("Işık hızı sabittir.", ["ışık", "hızı", "sabittir"]),
        (
            "TÜRKİYE'DE 2024 YILINDA SEÇİM VAR.",
            ["türkiye", "yılında", "seçim", "var"],
        ),
        ("Merhaba, dünya! Nasılsın??", ["merhaba", "dünya", "nasılsın"]),
        (
            "Çanakkale Boğazı çok önemli bir su yoludur.",
            ["çanakkale", "boğazı", "çok", "önemli", "bir", "su", "yoludur"],
        ),
        (
            "Ali'nin arabası kırmızı, Veli'ninki mavi.",
            ["ali", "arabası", "kırmızı", "veli", "mavi"],
        ),
        ("Öğretmen öğrencilere ödev verdi.", ["öğretmen", "öğrencilere", "ödev", "verdi"]),
        ("Şu anda saat 14:30.", ["şu", "anda", "saat"]),
        ("Ekonomi %5 büyüdü.", ["ekonomi", "büyüdü"]),
        # Edge case'ler
        ("Iğdır'dan İzmir'e gidildi.", ["ığdır", "izmir", "gidildi"]),
        ("TÜM HARFLER BÜYÜK", ["tüm", "harfler", "büyük"]),
        ("Türkiye'", ["türkiye"]),  # apostrof var, sonrası boş
        ("'nin bir şeyi yok.", ["bir", "şeyi", "yok"]),  # apostrof kelime başında
        ("!!! ... ???", []),  # salt noktalama
        ("", []),  # boş string
        ("2024 2025 2026", []),  # salt sayı
        ("   \t\n  ", []),  # sadece boşluk
    ],
)
def test_tokenize(metin: str, beklenen: list[str]) -> None:
    assert tokenize(metin) == beklenen


@pytest.mark.parametrize(
    ("girdi", "beklenen"),
    [
        ("I", "ı"),
        ("İ", "i"),
        ("IĞDIR", "ığdır"),
        ("İZMİR", "izmir"),
    ],
)
def test_turkish_lower_i_ayrimi(girdi: str, beklenen: str) -> None:
    assert turkish_lower(girdi) == beklenen
