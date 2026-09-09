# Bilinen Sınırlamalar

- **Tireli birleşik kelimeler (Faz 1 tokenizer):** `tokenize()` apostrof
  dışındaki tüm harf-olmayan karakterleri sessizce atıyor, split noktası
  olarak kullanmıyor. Bu yüzden `"anayasa-mahkemesi"` gibi tireli kelimeler
  `"anayasamahkemesi"` şeklinde tek token'a düşüyor. Şimdilik bilinçli
  olarak ertelendi — Faz 2'de gerçek Wikipedia korpusuyla karşılaşınca ne
  sıklıkla sorun çıkardığına bakıp karar verilecek.

- **Operatörsüz yan yana yazım (Faz 5 sorgu ayrıştırıcı):** `"kedi köpek"`
  gibi aralarında `AND`/`OR` olmayan bir sorgu **parse hatası** verir —
  örtük bir AND/OR varsayılmıyor. Bilinçli bir tercih: SPEC'in "anlaşılan
  kod" önceliğine sadık kalıp sessiz bir varsayım eklememek için. Faz 6'da
  (FastAPI MVP) gerçek kullanım sonrası, kullanıcı deneyimi açısından
  gerçekten gerekli olup olmadığına bakılıp karar verilecek.

- **Redis cache, gerçek Redis'e karşı doğrulanmadı (Faz 9):** Geliştirme
  ortamında ne gerçek bir Redis sunucusu, ne Docker, ne de çalışır
  durumda bir WSL var (sanallaştırma servisi kapalı). `AramaCache`
  (`src/shardsearch/api/cache.py`) redis-py'nin gerçek API'sine karşı
  yazıldı ve gerçek Redis'le birebir aynı şekilde çalışması beklenir, ama
  hem otomatik testlerde hem bu oturumdaki manuel doğrulamada `fakeredis`
  (bellek içi, redis-py protokolünü taklit eden bir test kütüphanesi)
  kullanıldı. Gerçek ağ round-trip'i, bağlantı kopması/timeout davranışı,
  gerçek TTL süresi hassasiyeti hiç test edilmedi. WSL düzeltilince ya da
  Docker Desktop kurulup bağımsız çalışınca, aynı test suite'i
  (`tests/unit/test_cache.py`, `tests/unit/test_api.py`'deki cache
  testleri) `SHARDSEARCH_REDIS_URL` gerçek bir sunucuyu gösterecek şekilde
  gerçek Redis'e karşı çalıştırılıp bu not kapatılmalı.
