"""Phase 1 tests: does tokenize() produce the expected token list.

Expected values were computed by hand: first turkish_lower, then taking
everything before an apostrophe, then keeping only letters.
"""

import pytest

from shardsearch.tokenizer import tokenize, turkish_lower


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 10 different Turkish sentences
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
        # Edge cases
        ("Iğdır'dan İzmir'e gidildi.", ["ığdır", "izmir", "gidildi"]),
        ("TÜM HARFLER BÜYÜK", ["tüm", "harfler", "büyük"]),
        ("Türkiye'", ["türkiye"]),  # apostrophe present, nothing after it
        ("'nin bir şeyi yok.", ["bir", "şeyi", "yok"]),  # apostrophe at the start of a word
        ("!!! ... ???", []),  # punctuation only
        ("", []),  # empty string
        ("2024 2025 2026", []),  # digits only
        ("   \t\n  ", []),  # whitespace only
    ],
)
def test_tokenize(text: str, expected: list[str]) -> None:
    assert tokenize(text) == expected


@pytest.mark.parametrize(
    ("input_", "expected"),
    [
        ("I", "ı"),
        ("İ", "i"),
        ("IĞDIR", "ığdır"),
        ("İZMİR", "izmir"),
    ],
)
def test_turkish_lower_i_distinction(input_: str, expected: str) -> None:
    assert turkish_lower(input_) == expected
