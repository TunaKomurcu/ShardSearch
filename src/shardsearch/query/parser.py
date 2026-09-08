"""Boolean sorgu dizgisini ayrıştırma ağacına çeviren recursive-descent parser.

Gramer (öncelik, en dışta en düşük olacak şekilde kodlanmış):

    sorgu := veya
    veya  := ve (OR ve)*        # AND'den daha düşük öncelik
    ve    := terim (AND terim)* # OR'dan daha sıkı bağlanır
    terim := KELIME | "IFADE" | ( sorgu )

AND'in OR'dan sıkı bağlanması bilinçli bir seçim: SQL, Lucene/Elasticsearch
klasik sözdizimi ve genel olarak programlama dillerindeki and/or önceliğiyle
aynı kural. "a AND b OR c" bu yüzden "(a AND b) OR c" olarak ayrıştırılır.

Operatörsüz yan yana yazım ("kedi köpek", aralarında AND/OR yok) bilinçli
olarak DESTEKLENMİYOR — örtük bir operatör varsaymak yerine SorguHatasi
fırlatılıyor (bkz. docs/known-limitations.md).
"""

import re

from shardsearch.query.ast import Ifade, SorguDugumu, Terim, Ve, Veya
from shardsearch.tokenizer import tokenize

_TOKEN_REGEX = re.compile(r'"[^"]*"|[()]|[^\s()]+')


class SorguHatasi(Exception):
    pass


def _sorgu_tokenlestir(sorgu_metni: str) -> list[tuple[str, str]]:
    """Ham sorgu dizgisini (tür, deger) çiftlerine böler.

    Tür şunlardan biri: PHRASE, LPAREN, RPAREN, AND, OR, WORD.
    AND/OR büyük/küçük harf duyarsız tanınır (kullanıcı "and"/"or" da
    yazabilir); WORD ve PHRASE içeriği burada normalize edilmez, bu iş
    parser'da _terim()'e bırakılır.
    """
    tokenler: list[tuple[str, str]] = []
    for parca in _TOKEN_REGEX.findall(sorgu_metni):
        if parca.startswith('"'):
            tokenler.append(("PHRASE", parca[1:-1]))
        elif parca == "(":
            tokenler.append(("LPAREN", parca))
        elif parca == ")":
            tokenler.append(("RPAREN", parca))
        elif parca.upper() == "AND":
            tokenler.append(("AND", parca))
        elif parca.upper() == "OR":
            tokenler.append(("OR", parca))
        else:
            tokenler.append(("WORD", parca))
    return tokenler


class _SorguAyristirici:
    def __init__(self, tokenler: list[tuple[str, str]]) -> None:
        self._tokenler = tokenler
        self._pos = 0

    def _mevcut(self) -> tuple[str, str] | None:
        if self._pos < len(self._tokenler):
            return self._tokenler[self._pos]
        return None

    def _ilerle(self) -> tuple[str, str]:
        token = self._mevcut()
        if token is None:
            raise SorguHatasi("Sorgu beklenenden erken bitti")
        self._pos += 1
        return token

    def ayristir(self) -> SorguDugumu:
        if self._mevcut() is None:
            raise SorguHatasi("Boş sorgu")
        dugum = self._veya()
        if self._mevcut() is not None:
            raise SorguHatasi(
                f"Beklenmeyen token, muhtemelen aralarında AND/OR olmayan iki "
                f"terim yan yana yazılmış: {self._mevcut()}"
            )
        return dugum

    def _veya(self) -> SorguDugumu:
        sol = self._ve()
        while self._mevcut() is not None and self._mevcut()[0] == "OR":
            self._ilerle()
            sag = self._ve()
            sol = Veya(sol, sag)
        return sol

    def _ve(self) -> SorguDugumu:
        sol = self._terim()
        while self._mevcut() is not None and self._mevcut()[0] == "AND":
            self._ilerle()
            sag = self._terim()
            sol = Ve(sol, sag)
        return sol

    def _terim(self) -> SorguDugumu:
        token = self._mevcut()
        if token is None:
            raise SorguHatasi("Terim beklenirken sorgu bitti")
        tur, deger = token

        if tur == "LPAREN":
            self._ilerle()
            dugum = self._veya()
            kapanis = self._mevcut()
            if kapanis is None or kapanis[0] != "RPAREN":
                raise SorguHatasi("Kapanan parantez ')' bekleniyordu")
            self._ilerle()
            return dugum

        if tur == "PHRASE":
            self._ilerle()
            return Ifade(tuple(tokenize(deger)))

        if tur == "WORD":
            self._ilerle()
            kelimeler = tokenize(deger)
            return Terim(kelimeler[0] if kelimeler else "")

        raise SorguHatasi(f"Terim beklenirken beklenmeyen token: {token}")


def ayristir(sorgu_metni: str) -> SorguDugumu:
    return _SorguAyristirici(_sorgu_tokenlestir(sorgu_metni)).ayristir()
