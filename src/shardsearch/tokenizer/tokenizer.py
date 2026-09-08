"""Basit kural tabanlı Türkçe tokenizer.

SPEC.md'nin kapsamı: gelişmiş morfolojik analiz değil, basit kurallar.
Uygulanan üç kural:

1. Türkçe-farkında küçük harfe çevirme (bkz. casing.turkish_lower).
2. Apostrof kuralı: Türkçe yazım kuralında özel isim + ek apostrofla
   ayrılır ("Türkiye'nin"). Kökü ekten ayırmak için gelişmiş morfoloji
   gerekir; bunun yerine en basit kural uygulanıyor: apostroftan
   ÖNCESİNİ token olarak al, ekini at. Apostrof kelimenin en başındaysa
   (ör. "'nin") öncesi boş kalır ve token tamamen düşer — aynı kuralın
   simetrik sonucu, ayrı bir özel durum değil.
3. Noktalama ve sayı temizliği: token'dan yalnızca harfler tutulur,
   harf olmayan her şey (noktalama + rakamlar) atılır. Bu, salt sayısal
   token'ları da kendiliğinden eler (ör. "2024" -> "").
"""

from shardsearch.tokenizer.casing import turkish_lower

_APOSTROFLAR = ("'", "’", "‘", "´", "`")


def _parcayi_temizle(parca: str) -> str:
    for apostrof in _APOSTROFLAR:
        idx = parca.find(apostrof)
        if idx != -1:
            parca = parca[:idx]
            break
    return "".join(ch for ch in parca if ch.isalpha())


def tokenize(text: str) -> list[str]:
    normalized = turkish_lower(text)
    tokens = (_parcayi_temizle(parca) for parca in normalized.split())
    return [token for token in tokens if token]
