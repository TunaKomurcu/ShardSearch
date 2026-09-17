"""Simple rule-based Turkish tokenizer.

SPEC.md's scope: simple rules, not advanced morphological analysis.
Three rules are applied:

1. Turkish-aware lowercasing (see casing.turkish_lower).
2. Apostrophe rule: in Turkish orthography, a proper noun plus suffix is
   separated by an apostrophe ("Türkiye'nin"). Splitting the stem from
   the suffix properly requires morphological analysis; instead we apply
   the simplest possible rule: take everything BEFORE the apostrophe as
   the token, drop the suffix. If the apostrophe is at the very start of
   the word (e.g. "'nin"), the part before it is empty and the token is
   dropped entirely — a symmetric result of the same rule, not a
   separate special case.
3. Punctuation and digit stripping: only letters are kept in a token,
   everything else (punctuation + digits) is discarded. This also
   naturally eliminates purely numeric tokens (e.g. "2024" -> "").
"""

from shardsearch.tokenizer.casing import turkish_lower

_APOSTROPHES = ("'", "’", "‘", "´", "`")


def _clean_chunk(chunk: str) -> str:
    for apostrophe in _APOSTROPHES:
        idx = chunk.find(apostrophe)
        if idx != -1:
            chunk = chunk[:idx]
            break
    return "".join(ch for ch in chunk if ch.isalpha())


def tokenize(text: str) -> list[str]:
    normalized = turkish_lower(text)
    tokens = (_clean_chunk(chunk) for chunk in normalized.split())
    return [token for token in tokens if token]
