# PHASES.md — Aşama Aşama Yol Haritası

Her faz, bir öncekinin üzerine inşa edilir. Bir faz "Definition of Done" kriterini karşılamadan bir sonrakine geçilmez.

## Faz 0: Kurulum ✅ (Tamamlandı)
- Proje iskeleti (`src/`, `tests/`, `benchmarks/`, `docs/` klasörleri)
- Bağımlılık yönetimi kurulumu (uv veya poetry)
- pytest, ruff/black kurulumu
- **Definition of Done:** `pytest` (boş test seti olsa bile) hatasız çalışıyor, `git init` yapılmış

## Faz 1: Tokenizer
- Metni token'lara ayırma, küçük harfe çevirme (Türkçe İ/ı farkındalığıyla — `.lower()` Türkçe'de hatalı sonuç verir, bunu bilerek çöz), noktalama/sayı temizleme
- **Test:** en az 10 farklı Türkçe cümle + edge case'ler (büyük İ, apostroflu kelimeler — "Türkiye'nin", sayı içeren metin)
- **Definition of Done:** tüm test cümleleri beklenen token listesini üretiyor

## Faz 2: Ters İndeks (bellek içi)
- `token → [(belge_id, frekans, [pozisyonlar])]` veri yapısı
- **Test:** küçük bir test korpusunda (10-20 cümle), bilinen bir kelimenin doğru belgelerde, doğru frekansla bulunması
- **Definition of Done:** postings listesi manuel hesaplanan beklenen değerle birebir eşleşiyor

## Faz 3: BM25 Skorlama
- TF, IDF, belge uzunluğu normalizasyonu — formülün her parçası ayrı fonksiyon, ayrı test
- **Doğrulama:** aynı korpusta `rank_bm25` (sadece `tests/validation/`'da) ile üretilen skorlarla karşılaştırma
- **Definition of Done:** kendi skorlarımızın sıralaması, referans kütüphaneninkiyle yüksek korelasyon gösteriyor (ilk 5 sonuç aynı sırada, ya da fark açıklanabilir)

## Faz 4: Kalıcı Depolama (SQLite)
- Ters indeksi SQLite'a yazma/okuma katmanı
- **Definition of Done:** uygulama kapanıp yeniden başlatıldığında indeks kayboluyor, bellekten değil diskten yükleniyor

## Faz 5: Sorgu Ayrıştırıcı
- `AND`/`OR` boolean mantık, `"ifade eşleştirme"` (phrase, pozisyon bilgisini kullanarak)
- **Test:** operatör önceliği açıkça test ediliyor (`a AND b OR c` — hangi sırayla değerlendiriliyor)
- **Definition of Done:** karmaşık bir sorgu string'i doğru ayrıştırma ağacına çevriliyor

## Faz 6: FastAPI Sarmalayıcı — İLK ÇALIŞAN MVP
- `POST /index` (belge ekleme), `GET /search` (arama) endpoint'leri
- **Definition of Done:** gerçek bir HTTP isteğiyle uçtan uca, tek-node arama çalışıyor — bu noktada "çalışan bir ürün" var

## Faz 7: Sharding
- Consistent hashing ile belge dağıtımı (hatırlarsan hash tablosu/sharding dersi)
- **Test:** belgeler shard'lara dengeli dağılıyor mu (dağılım istatistiği); shard sayısı değişince (resharding) minimum veri yer değiştiriyor mu
- **Definition of Done:** N shard'a dağıtılmış veri, hangi shard'da olduğu doğru şekilde bulunabiliyor

## Faz 8: Dağıtık Sorgu (Fan-out + Birleştirme)
- asyncio ile paralel shard sorgulama, sonuçları birleştirip global sıralama
- **Test:** dağıtık sonuç ile tek-node sonucu karşılaştırması — IDF farkından kaynaklanan sapmalar açıklanabilir mi
- **Definition of Done:** 3 shard'lı dağıtık arama, tek-node sonucuyla tutarlı sonuç veriyor

## Faz 9: Cache Katmanı
- Redis ile sık tekrarlanan sorguları cache'leme (cache-aside deseni)
- **Definition of Done:** aynı sorgu ikinci kez ölçülebilir şekilde daha hızlı dönüyor

## Faz 10: Gözlemlenebilirlik + Yük Testi
- Yapılandırılmış log, sorgu süresi metrikleri (p50/p95/p99)
- Locust ile yük testi
- **Definition of Done:** Locust raporu + p50/p95/p99 grafiği elde edilmiş

## Faz 11 (Stretch — opsiyonel, zaman kalırsa)
- Zemberek ile gelişmiş Türkçe stemming
- `hnswlib`/`faiss` ile hibrit (BM25 + semantik) arama
- Dockerize etme, basit CI/CD kurulumu

---

## Her Faz Sonunda Beklenen Çıktı

1. Çalışan, test edilmiş kod
2. Kısa bir özet: bu fazda hangi tasarım kararları alındı, neden
3. `PHASES.md`'de ilgili maddenin işaretlenmesi
