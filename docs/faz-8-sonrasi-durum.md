# Faz 8 Sonrası Durum: Sistem Artık Gerçekten Dağıtık

`docs/mvp-ozet.md`'nin devamı. Faz 0-6 tek-node bir MVP kurmuştu; Faz 7-8
ile sistem artık gerçekten dağıtık: birden fazla bağımsız SQLite dosyası
(shard), consistent hashing ile belge dağıtımı, asyncio ile paralel
sorgulama. Bu doküman, bu noktada "ne inşa ettik, hangi garantiler var,
hangi bilinçli yaklaşıklıklar var" sorusuna tek bakışta cevap olsun diye.

## Ne değişti (Faz 6 MVP'ye göre)

| | Faz 6 (tek-node MVP) | Faz 8 sonrası |
|---|---|---|
| Depolama | Tek `SqliteTersIndeks`, tek `.db` | N bağımsız `SqliteTersIndeks`, `data/<shard_id>.db` |
| `/index` | Doğrudan tek indekse yazar | `TutarliHash.shard_bul()` ile doğru shard'a yönlendirilir |
| `/search` | Tek indekste `degerlendir()`+`bm25_skoru()` | Tüm shard'lara `asyncio.to_thread` ile paralel, sonuçlar birleştirilir |
| Hata durumu | Tek nokta — indeks çökerse arama çöker | Kısmi başarısızlık tolere edilir, `basarisiz_shardlar` ile raporlanır |

## Garanti edilen şey: aday belge kümesi tutarlılığı

`degerlendir()` (AND/OR/phrase eşleştirme) sadece postings'in **varlığına
ve pozisyonuna** bakar, hiç skor hesaplamaz. Bu yüzden "bir sorguya hangi
belgeler eşleşiyor" sorusunun cevabı, verinin kaç shard'a bölündüğünden
**tamamen bağımsızdır** — şansa değil, algoritmanın yapısına dayanan bir
garanti. `tests/unit/test_fan_out.py::test_dengeli_dagitimda_aday_kumesi_tek_node_ile_birebir_ayni`
bunu 6 farklı sorgu tipinde (tek terim, AND, OR, phrase) doğruluyor.

## Bilinçli yaklaşıklık: yerel (shard-başına) IDF

BM25'in IDF'i global korpus istatistiği (toplam belge sayısı, terimi
içeren belge sayısı) gerektirir. Her shard SADECE KENDİ belgelerine göre
IDF hesaplıyor (Elasticsearch'ün varsayılan davranışı ile aynı — global
istatistik toplamak için ikinci bir round-trip yok). Sonuç: **sıralama**
(skorların göreli düzeni) tek-node'dan sapabilir, **aday küme** sapmaz.

Ölçülmüş iki gözlem:

1. **Dengeli dağıtımda küçük sapma:** 12 belgelik korpus, consistent
   hashing ile 3 shard'a dengeli dağıtılınca bile "kedi OR köpek"
   sorgusunda bir belgenin sırası (2.'den 4.'e) değişebiliyor.
2. **Dengesiz dağıtımda büyük sapma:** bir terimi içeren belgelerin
   çoğu tek bir (küçük) shard'a toplanırsa, o shard'daki yerel IDF
   global IDF'nin **5 katından fazla** sapabiliyor — çünkü terim o küçük
   shard'da orantısız "yaygın" görünüyor.

**Sebep-sonuç ilişkisi kanıtlandı, sadece iddia edilmedi:** sapmanın
büyüklüğü shard'lar arası terim dağılımının dengesizliğiyle doğru
orantılı — büyük, terim dağılımı dengeli korpuslarda küçülmesi beklenir
(büyük sayılar yasası), küçük/dengesiz korpuslarda büyütecin altında
görünür. Detaylar ve testler: `src/shardsearch/distributed/fan_out.py`
docstring'i, `tests/unit/test_fan_out.py`.

## Henüz yapılmayanlar (sıradaki fazlar)

- **Cache** (Faz 9) — sık tekrarlanan sorgular her seferinde tüm
  shard'ları tekrar tekrar sorguluyor.
- **Gözlemlenebilirlik / yük testi** (Faz 10) — thread-safety kilidinin
  (bkz. `docs/mvp-ozet.md`) gerçek eşzamanlı yük altında nasıl davrandığı
  hâlâ bilinmiyor.
- **Resharding'in canlı sisteme etkisi** — Faz 7 resharding'in
  matematiksel olarak minimum veri taşıdığını kanıtladı, ama çalışan
  API'de bir shard eklendiğinde/çıkarıldığında verinin fiilen yeniden
  dağıtılması (mevcut `.db` dosyalarından taşınması) hiç implement
  edilmedi — bu, SPEC.md'nin kapsamında da yoktu, olası bir stretch.
