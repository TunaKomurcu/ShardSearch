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

- **Redis erişilemezken eşzamanlı yük altında ciddi gecikme büyümesi (Faz
  10, ÇÖZÜLMEDİ):** Faz 10'un gerçek Locust koşusunda bulundu — Redis
  yokken (bu ortamın durumu) tek bir izole istek `/search`'te ~0.4-1.6sn
  sürüyor (redis-py'nin bağlantı-reddedildi durumunu ele alışı, bkz.
  `app.py`'deki `_redis_istemcisi_olustur()` yorumu — `socket_connect_timeout`
  ile 4sn'den bu seviyeye indirildi). Ama Locust ile GERÇEK eşzamanlı yük
  altında (8-30 kullanıcı), gecikme zamanla **sınırsız büyüyor** (450ms →
  25 saniyeye kadar 60sn içinde) — klasik bir kuyruk birikmesi imzası,
  gelen istek oranı sunucunun işleyebildiği oranı aşıyor.

  **Ne denendi, ne elendi:** Önce şüphelenilen `SqliteTersIndeks`'in
  `threading.Lock`'ı (bkz. Faz 6/9 notları) — izole testlerle ELENDİ:
  hem ayrı Redis istemcileriyle hem TEK PAYLAŞILAN Redis istemcisiyle 30
  eşzamanlı çağrı doğrudan Python'da denendiğinde ikisi de ~0.45-0.49
  saniyede (paralel, serileşmeden) tamamlandı — SqliteTersIndeks'e hiç
  dokunulmadan bile. Yani sorun ne bizim kilit mekanizmamızda, ne de tek
  başına Redis istemcisinde izole halde.

  **Kök neden tam olarak bulunamadı** — muhtemel aday: FastAPI/Starlette'in
  senkron route'lar için kullandığı thread pool (anyio) ile `asyncio.to_thread`'in
  (fan-out'ta shard başına kullanılan, bkz. `distributed/fan_out.py`)
  kullandığı AYRI varsayılan thread pool'un bu ortamın Redis-yok
  senaryosunda (her istek ~0.4-1.6sn bir worker thread'i bloke ediyor)
  birlikte nasıl davrandığı — ama bu kesinleşmedi, sadece bir hipotez.

  **Neden bu fazda düzeltilmedi:** Kök nedeni kesin olarak izole etmek
  (Starlette/anyio thread pool boyutlandırması, asyncio executor'ı, gerçek
  Redis varken bu ortamda tekrar test etme) SPEC kapsamının ötesinde bir
  derinlik gerektiriyor — connection pool kurmak gibi, bu fazın "ölç ve
  raporla" sınırının dışında. Gerçek Redis erişimi olduğunda (bkz. yukarıki
  madde) bu senaryo TEKRAR test edilmeli: sorun Redis'in yokluğuna özgüyse
  gerçek Redis'le tamamen kaybolacaktır, değilse (asıl endişe konusu olan
  Starlette/asyncio thread pool etkileşimiyse) o zaman gerçek bir
  mimari inceleme gerekecektir.

  **Somut sonraki adım (ipucu kaybolmasın diye):** `GET /search` route'u
  şu an zaten `async def` (bkz. `app.py`) ama içindeki `dagitik_ara()`
  her shard için ayrı bir `asyncio.to_thread()` çağrısı yapıyor — bunun
  kullandığı varsayılan `asyncio` executor'ı ile Starlette'in `POST
  /index` gibi SENKRON (`def`) route'lar için kullandığı ayrı anyio
  thread pool'unun bu ortamda birbiriyle nasıl etkileştiğini test etmek
  gerekiyor. Denenecek somut deney: `/index`'i de `async def`'e çevirip
  (SqliteTersIndeks çağrısını `asyncio.to_thread` ile sarmalayarak) TEK
  bir thread pool mekanizmasına indirmek, aynı Locust senaryosunu tekrar
  koşup gecikme büyüme paterninin (450ms → 25sn) azalıp azalmadığını
  ölçmek — bu, iki ayrı thread pool'un çakışmasının gerçek neden olup
  olmadığını doğrudan test eder.
