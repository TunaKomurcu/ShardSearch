"""API'nin istek/yanıt sözleşmesi (Pydantic modelleri)."""

from pydantic import BaseModel


class BelgeEkleIstegi(BaseModel):
    belge_id: str
    metin: str


class BelgeEkleYaniti(BaseModel):
    belge_id: str
    durum: str


class AramaSonucu(BaseModel):
    belge_id: str
    skor: float
    # MVP kapsamında snippet değil TAM metin dönüyor — bilinçli bir kapsam
    # kararı. Üretimde muhtemelen belgenin tamamı değil, sorguyla eşleşen
    # kısmın etrafında kısa bir snippet dönülür (vurgulama/highlighting ile
    # birlikte); bu, kendi başına ayrı bir özellik ve şimdilik kapsam dışı.
    metin: str


class AramaYaniti(BaseModel):
    sorgu: str
    sonuclar: list[AramaSonucu]
    # Faz 8: bir veya daha fazla shard sorgu sırasında hata verirse burada
    # AÇIKÇA listelenir — sessiz veri kaybı yerine, "eksik ama neden eksik
    # olduğu bilinen" kısmi bir sonuç. Boş liste = tüm shard'lar cevap verdi.
    basarisiz_shardlar: list[str] = []


class HataYaniti(BaseModel):
    hata: str
