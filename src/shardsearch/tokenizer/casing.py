"""Turkish-specific letter lowercasing.

Python's built-in str.lower() applies English/Latin casing rules:
'I' -> 'i' and 'İ' -> 'i̇' (i + U+0307 combining dot above). In Turkish,
I/ı and İ/i are two independent letter pairs — the lowercase of 'I' is
'ı', and the lowercase of 'İ' is 'i'. Ignoring this distinction turns
"Işık" (ışık, correct) into "işık" (a different, incorrect word). The
other Turkish letters (Ç/Ğ/Ö/Ş/Ü) already map correctly with the
standard .lower(), so only I/İ need a special case.
"""

_SPECIAL_UPPER_TO_LOWER = {
    "I": "ı",
    "İ": "i",
}


def turkish_lower(text: str) -> str:
    return "".join(_SPECIAL_UPPER_TO_LOWER.get(ch, ch.lower()) for ch in text)
