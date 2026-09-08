# CLAUDE.md — Bu Depoda Çalışırken Uyulacak Kurallar

## Bu projenin doğası

Bu bir **öğrenme projesi**, üretim ürünü değil. Kullanıcı bir AI mühendisi, backend/dağıtık sistemler derinliği kazanmak istiyor. Önceliğin **kullanıcının anlaması** — hızlı, sessiz kod üretmek değil.

- Her önemli fonksiyonu yazarken, **neden** o şekilde tasarlandığını açıklayan yorum/docstring ekle (ne yaptığı değil, hangi kararla o şekilde yazıldığı)
- Karmaşık bir algoritma (BM25, consistent hashing gibi) yazarken, kodun üstüne kısa bir "bu neden böyle çalışıyor" açıklaması ekle
- Kullanıcı anlamadan bir sonraki adıma geçme — özetle, onay iste

## KESİNLİKLE KULLANMA — Yasak Kısayollar

Aşağıdakileri önerme, kurma, importlama. Kullanıcı bunları bilerek yasakladı çünkü projenin tüm amacı bunları **sıfırdan yazmak**:

- ❌ Elasticsearch, OpenSearch, Solr, Whoosh — hiçbir hazır arama motoru/kütüphanesi
- ❌ `rank_bm25` veya benzeri hazır BM25 kütüphaneleri — **istisna:** SADECE `tests/validation/` klasöründe, kendi implementasyonumuzu doğrulamak için referans olarak kullanılabilir, ana koda (`src/`) asla girmez
- ❌ Raft, Paxos, etcd, Consul gibi dinamik cluster coordination araçları — shard ataması SPEC.md'de belirtildiği gibi **statik, config dosyasında** tanımlı kalacak
- ❌ Kendi HNSW/vektör indeks implementasyonu — SPEC.md'de "kapsam dışı" olarak işaretli
- ❌ Gelişmiş Türkçe morfolojik analiz kütüphaneleri (Zemberek dahil) — sadece SPEC.md'de "ileride, opsiyonel" olarak işaretlenmiş, şimdilik basit kurallı tokenizer yeterli

**Eğer bir görevi çözmek için yukarıdakilerden birini kullanmak "daha kolay/hızlı" görünüyorsa, DURMA — kullanıcıya bunu neden önerdiğini açıkla ve onay bekle. Sessizce kısayol alma.**

## Çalışma Şekli

1. Her faza başlamadan önce `PHASES.md`'deki ilgili fazı oku, o fazın "Definition of Done" kısmını hedef al
2. Büyük bir kod bloğu yazmadan önce, planı **2-3 cümleyle özetle**, kullanıcının onayını bekle
3. Her faz için unit test yaz — testler geçmeden bir sonraki faza geçme
4. Türkçe karakter (ı/İ, ş/ğ/ü/ö/ç) içeren test case'lerini her zaman ekle, unutma
5. Bir fazı bitirdiğinde, `PHASES.md`'deki ilgili maddeyi işaretle ve kullanıcıya kısa bir özet ver: ne yapıldı, hangi tasarım kararları alındı, sırada ne var

## Kod Stili

- Python, tam tip belirteçleriyle (type hints)
- Fonksiyonlar küçük, tek sorumluluklu (SOLID'in Single Responsibility ilkesi)
- Karmaşık algoritmaların (BM25 formülü gibi) her parametresi için kısa bir açıklama yorumu

## Git

- Her faz kendi branch'inde (`faz-1-tokenizer` gibi), faz bitip onaylanınca `main`'e merge
- Commit mesajları: `faz-N: kısa açıklama` formatında

## Belirsizlik Durumunda

Kapsam dışı bir şeye ihtiyaç olduğunu düşünürsen (SPEC.md'de olmayan bir kütüphane, yeni bir bağımlılık), **asla sessizce ekleme** — önce kullanıcıya sor, gerekçeni açıkla.

## Tasarım Kararlarında Onay Eşiği

- **Veri modelini veya sorgu sözleşmesini değiştiren kararlar** (ör. operatör önceliği, hangi sözdizimi hata verir, şema değişiklikleri) — her zaman önce sor, kod yazmadan onay bekle. Bunlar geri alınması pahalı ve kullanıcının gerçekten karar vermek isteyeceği türden seçimler.
- **Sadece kullanıcı deneyimi esnekliği sağlayan, geri alınması bedava kararlar** (ör. `AND`/`OR` anahtar kelimelerinin büyük/küçük harf duyarsız olması) — dokümante ederek (kod yorumu ve/veya `docs/`) devam edilebilir, ayrı onay gerekmez.
