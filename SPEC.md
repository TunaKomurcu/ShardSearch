# SPEC.md — ShardSearch Proje Spesifikasyonu

## Amaç

Sıfırdan, dağıtık çalışabilen bir metin arama motoru inşa etmek. Bu **üretime hazır bir Elasticsearch alternatifi değil** — amaç, arama motorlarının temel mekanizmalarını (ters indeks, BM25, sharding, dağıtık sorgu birleştirme) gerçekten anlayarak, kendi elimizle inşa etmek. Öncelik: **doğru çalışan kod değil, anlaşılan kod.**

## Neden bu proje?

- Hash tablosu, BM25, consistent hashing, asyncio, sharding gibi daha önce "kütüphane olarak kullanılan" kavramları, alttaki mekanizmayı gerçekten inşa ederek öğrenmek
- Alan bilgisi (domain knowledge) gerektirmiyor — tamamen mühendislik derinliği odaklı
- BM25/hibrit retrieval tecrübesini "kullanıyorum" seviyesinden "neden öyle çalıştığını biliyorum" seviyesine taşımak

## Kapsam İçi — Sıfırdan Yazılacak

1. **Tokenizer** — Türkçe-farkında, basit kural tabanlı (gelişmiş morfoloji analizi değil)
2. **Ters İndeks** — token → (belge_id, frekans, pozisyon listesi) veri yapısı
3. **BM25 Sıralama Algoritması** — TF, IDF, belge uzunluğu normalizasyonu, elle implementasyon
4. **Sorgu Ayrıştırıcı** — AND/OR boolean mantık + ifade (phrase) eşleştirme
5. **Sharding** — consistent hashing ile belge dağıtımı
6. **Dağıtık Sorgu** — asyncio ile paralel shard sorgulama (fan-out) + sonuç birleştirme (merge)

## Kapsam Dışı — Hazır Araç Kullanılacak veya Hiç Yapılmayacak

| Bileşen | Karar | Gerekçe |
|---|---|---|
| Web/API katmanı | FastAPI kullan | Framework'ün var oluş sebebi — sıfırdan HTTP sunucusu yazmak kapsam dışı |
| Kalıcı depolama | SQLite kullan | Kendi B-tree/LSM-tree yazmak ayrı, devasa bir proje |
| Sorgu cache | Redis kullan | Cache mekanizması zaten ayrı derste işlendi, burada tekrar sıfırdan yazmaya gerek yok |
| Cluster coordination | Statik, config-tabanlı shard ataması | Raft/Paxos gibi dinamik konsensüs protokolleri kapsam dışı |
| Türkçe morfolojik analiz | Basit kurallarla başla, ileride opsiyonel Zemberek | Sıfırdan Türkçe stemming ayrı bir NLP araştırma projesi |
| Vektör/semantik arama | Opsiyonel stretch goal, `hnswlib`/`faiss` kullan | Kendi HNSW'ini yazmak kapsam dışı |
| Kimlik doğrulama, çoklu-kiracılık | Yok | Bu bir teknik demo, prod SaaS değil |

## Mimari (yüksek seviye)

```
İndeksleme yolu:
  Belge → Tokenizer (kendi) → Ters İndeks Kurucu (kendi) → SQLite (hazır depolama)

Sorgu yolu:
  İstemci → FastAPI (hazır) → Sorgu Ayrıştırıcı (kendi) → Shard'lara fan-out (kendi, asyncio)
    → [Shard 1, Shard 2, Shard 3] (her biri kendi BM25 hesaplar) → Sonuç birleştirme (kendi)
    → Redis cache (hazır) → Yanıt
```

## Teknoloji Yığını

- Python 3.12, tip belirteçleriyle (type hints)
- FastAPI (API katmanı)
- SQLite (kalıcı depolama)
- Redis (sorgu cache — Faz 9'dan itibaren)
- pytest (test), Locust (yük testi — Faz 10'dan itibaren)
- asyncio (dağıtık fan-out)

## Doğrulama Stratejisi (kritik — bu proje için özellikle önemli)

Kendi BM25 implementasyonumuzun **doğru** çalıştığını nasıl bileceğiz? "Çalışıyor" (hata vermiyor) ile "doğru çalışıyor" (doğru sonucu üretiyor) çok farklı şeyler. Çözüm: aynı küçük test korpusunda, `rank_bm25` kütüphanesiyle üretilen skorlarla **karşılaştırma testi** yazacağız. Bu kütüphane asla ana koda entegre edilmeyecek — sadece ayrı bir doğrulama/karşılaştırma dosyasında, referans olarak kullanılacak.

## Referans Veri Seti

Rastgele/sentetik veri değil, **gerçek bir Türkçe metin korpusu** (örn. Türkçe Wikipedia'dan alınmış 200-500 makale) kullanılacak — böylece "alaka düzeyi" (relevance) gerçek anlam taşıyor, sonuçları göz kararı da değerlendirebiliyoruz.

## Başarı Kriterleri

- Faz 6 sonunda: gerçek bir HTTP isteğiyle uçtan uca, tek-node arama çalışıyor
- Faz 8 sonunda: 3 shard'a dağıtılmış veri üzerinde, tek-node sonuçlarıyla tutarlı (açıklanabilir farklarla) dağıtık arama çalışıyor
- Faz 10 sonunda: Locust ile yük testi yapılmış, p50/p95/p99 gecikme metrikleri ölçülmüş
