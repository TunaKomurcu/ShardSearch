"""Türkçe'ye özel harf küçültme.

Python'un yerleşik str.lower() İngilizce/Latin kurallarını uygular:
'I' -> 'i' ve 'İ' -> 'i̇' (i + U+0307 birleşik nokta) üretir. Türkçe'de
ise I/ı ve İ/i birbirinden bağımsız iki harf çiftidir — 'I'nin küçüğü
'ı', 'İ'nin küçüğü 'i'dir. Bu farkı gözetmezsek "Işık" (ışık, doğru)
yerine "işık" (yanlış kelime) üretiriz. Diğer Türkçe harfler (Ç/Ğ/Ö/Ş/Ü)
zaten standart .lower() ile doğru eşleniyor, bu yüzden sadece I/İ için
özel durum tanımlamak yeterli.
"""

_OZEL_BUYUKTEN_KUCUGE = {
    "I": "ı",
    "İ": "i",
}


def turkish_lower(text: str) -> str:
    return "".join(_OZEL_BUYUKTEN_KUCUGE.get(ch, ch.lower()) for ch in text)
