# MVP Özeti (Faz 0-6 sonu)

Bu doküman, Faz 7'ye geçmeden önce bir mola notu: buraya kadar hangi
fazların neyi kapsadığı, hangi bilinçli kapsam dışı kararların alındığı.
İleride bu repoya bakan biri (ya da gelecekteki biz) "neden burada
durduk, neden buradan devam ediyoruz" sorusuna hızlı cevap bulsun diye.

## Buraya kadar ne inşa edildi

| Faz | Ne | Nerede |
|---|---|---|
| 0 | Proje iskeleti, uv, pytest, ruff | — |
| 1 | Türkçe-farkında tokenizer (İ/ı ayrımı, apostrof kuralı) | `src/shardsearch/tokenizer/` |
| 2 | Bellek içi ters indeks (sıralı postings, upsert) | `src/shardsearch/index/` |
| 3 | BM25 skorlama (TF/IDF/uzunluk normu ayrı fonksiyonlar) | `src/shardsearch/scoring/` |
| 4 | SQLite ile kalıcı depolama (aynı arayüz, disk destekli) | `src/shardsearch/storage/` |
| 5 | Boolean sorgu ayrıştırıcı (AND/OR önceliği, phrase eşleştirme) | `src/shardsearch/query/` |
| 6 | FastAPI MVP: `POST /index`, `GET /search` — hepsini birbirine bağlıyor | `src/shardsearch/api/` |

Sonuç: tek makinede, gerçek bir HTTP isteğiyle, kendi yazdığımız
tokenizer + ters indeks + BM25 + boolean sorgu ayrıştırıcı üzerinden
çalışan bir arama motoru. `rank_bm25` sadece `tests/validation/`'da
referans olarak duruyor, hiç `src/`'ye girmedi (otomatik guard-test bunu
garanti ediyor).

## Bilinçli kapsam dışı bırakılanlar (aşırı mühendislik önleme)

Bunlar "unutuldu" değil, SPEC.md'de veya faz onaylarında bilerek
ertelendi — şu anki tek-node MVP için gereksizler:

- **Mikroservis mimarisi / ayrı süreçler** — tek FastAPI süreci, tek
  SQLite dosyası. Sharding (Faz 7) ve dağıtık sorgu (Faz 8) geldiğinde
  "birden fazla shard" kavramı gelecek ama yine tek makinede,
  Kubernetes/Docker Compose gibi bir orkestrasyon katmanı olmadan.
- **Kubernetes / konteynerizasyon** — SPEC.md'nin Faz 11 (stretch, opsiyonel)
  listesinde "Dockerize etme" var ama K8s hiç planlanmadı; bu proje bir
  dağıtım/altyapı öğrenme projesi değil, arama motoru mekanizmaları
  öğrenme projesi.
- **Dinamik cluster coordination (Raft/Paxos/etcd/Consul)** — CLAUDE.md'de
  açıkça yasak. Faz 7'nin shard ataması statik, config dosyasında
  tanımlı olacak.
- **Connection pool / gerçek eşzamanlılık optimizasyonu** — Faz 6'da
  SQLite erişimi tek bir `threading.Lock` ile serileştirildi. Faz 10'da
  gerçek Locust yük testiyle ölçüldü: eşzamanlı yük altında ciddi bir
  gecikme büyümesi VAR, ama izole testler bunun bu `threading.Lock`'tan
  KAYNAKLANMADIĞINI gösterdi (bkz. `docs/known-limitations.md`) — asıl
  kök neden bu ortama özgü Redis-erişilemez senaryosuyla ilgili görünüyor,
  kesin olarak izole edilemedi.
- **Kimlik doğrulama, çoklu-kiracılık, rate limiting** — SPEC.md'de
  "bu bir teknik demo, prod SaaS değil" diye açıkça kapsam dışı.
- **Kendi B-tree/LSM-tree, kendi HNSW, gelişmiş Türkçe morfoloji** —
  hepsi SPEC.md'de "hazır araç kullan ya da hiç yapma" olarak işaretli.
- **Sonuç snippet'i / vurgulama (highlighting)** — `/search` şu an
  belgenin tamamını dönüyor, üretimde olması gereken kısa/vurgulu
  snippet değil. Faz 6'nın bilinçli bir MVP kısayolu (bkz.
  `AramaSonucu.metin` alanının yorum satırı).
- **Operatörsüz sorgu (implicit AND/OR)** — bkz.
  `docs/known-limitations.md`, Faz 6 kullanımı sonrası tekrar
  değerlendirilecek.

## Neden buradan devam ediyoruz

MVP'nin amacı "bitmiş ürün" değil, **tek-node'da her bileşenin doğru
çalıştığını kanıtlamak** — bundan sonraki fazlar (7: sharding, 8: dağıtık
sorgu) bu tek-node temelin üzerine inşa ediliyor. Faz 8'in DoD'si
("3 shard'lı dağıtık arama, tek-node sonucuyla tutarlı") bu yüzden
buradaki tek-node davranışı referans alıyor.
