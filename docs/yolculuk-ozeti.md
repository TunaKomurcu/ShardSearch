# Yolculuk Özeti: Faz 0-9 Arasında Bulunan Gerçek Hatalar

`docs/mvp-ozet.md` ve `docs/faz-8-sonrasi-durum.md`'nin devamı — ama bu
ikisi "ne inşa edildi"ne odaklanıyordu, bu doküman özellikle **hangi
gerçek hatalar yapıldı, nasıl bulundu, nasıl çözüldü** sorusuna
odaklanıyor. Amaç: CV/portföy anlatımında ya da ileride benzer bir
sisteme bakarken "bunu daha önce görmüştüm, nasıl çözülmüştü"
diyebilmek.

Kronolojik sırayla, en öğretici olanlar:

## 1. Süreç hatası: faz branch'ini açmayı unutmak (Faz 2)

**Ne oldu:** Faz 2'yi (ters indeks) yanlışlıkla doğrudan `main` üzerinde
kodladım, `faz-2-ters-indeks` branch'ini açmayı atladım.

**Nasıl bulundu:** Commit sonrası `git branch` çıktısını kontrol ederken
fark edildi — otomatik bir araç değil, sadece "her fazdan sonra git
durumunu doğrula" alışkanlığı.

**Nasıl çözüldü:** Commit'i `git branch faz-2-ters-indeks` ile yeni bir
branch'e "taşıyıp" (aynı commit'i işaretleyip), `main`'i `git reset --hard`
ile bir önceki (Faz 1 sonrası) haline geri aldım. Push edilmemiş lokal
commit olduğu için veri kaybı riski yoktu — ama bu düzeltmeyi yaparken
"neden güvenli" olduğunu (commit başka bir branch'te hâlâ erişilebilir
kalıyor) açıkça gerekçelendirmek gerekti.

**Genel ders:** Disiplin kuralları (branch-per-phase gibi) otomatik
uygulanmıyorsa, ihlal edildiğinde fark edip düzeltmek için düzenli
"durum kontrolü" alışkanlığı gerekir — kuralın kendisi kadar, kuralın
ihlalini yakalama refleksi de önemli.

## 2. Sıralama/tie-break belirsizliği: BM25 sonuçlarında tanımsız sıra (Faz 3)

**Ne oldu:** `sirala()` fonksiyonu eşleşen belgeleri bir Python `set`'ten
topluyordu. Eşit BM25 skorlu iki belge olduğunda, hangisinin önce
geleceği `set`'in iç hash sırasına bağlıydı — deterministik (aynı process
içinde hep aynı sonucu verir) ama **anlamsız ve öngörülemez** bir sıraydı.

**Nasıl bulundu:** `rank_bm25` ile karşılaştırma testinde, `"bir
hayvandır"` sorgusunda iki belge (`d06`, `d08`) tam olarak eşit skor
aldı; bizim sıralamamız `[d08, d06]` verirken referans kütüphane
`[d06, d08]` veriyordu — testler bunu yakaladı.

**Nasıl çözüldü:** `skorlar.sort(key=lambda cift: (-cift[1], cift[0]))`
— skor eşitse `belge_id`'ye göre artan sırada, deterministik ve
açıklanabilir bir ikincil sıralama anahtarı eklendi.

**Genel ders:** "Aynı skor" durumu unutulması kolay bir edge case'dir;
küme/hash tabanlı veri yapılarından sıralı sonuç üretirken ikincil bir
sıralama anahtarı olmadan sonuç **tanımsız davranış** sergiler, hata
değil ama güvenilmez.

## 3. Test metodolojisi hatası: elma-armut karşılaştırması (Faz 8)

**Ne oldu:** Dağıtık arama ile tek-node arama sonuçlarını karşılaştırırken,
tek-node "referans" için Faz 3'ün eski `sirala()` fonksiyonunu kullandım.
Ama `sirala()` Faz 5'in AND/OR/phrase ayrıştırıcısını hiç bilmiyor — ham
sorguyu düz kelime listesine çevirip bag-of-words OR mantığıyla eşleştirir.
`dagitik_ara()` ise `ayristir()+degerlendir()+bm25_skoru()` üçlüsünü
kullanıyor. Sonuç: phrase sorgusunda (`'"bir hayvandır"'`), tek-node
"referansı" alakasız bir belgeyi (sadece "bir" kelimesini içeren, ama
"hayvandır" içermeyen) sonuca sızdırıyordu — dağıtık arama ise doğru
şekilde onu dışarıda bırakıyordu. Yani "hata" gerçek sistemde değil,
test metodolojisindeydi.

**Nasıl bulundu:** Karşılaştırma testini yazmadan önce ara sonuçları
elle (bir Python REPL'inde) inceleme alışkanlığı — beklenmeyen bir
belgenin sonuçta göründüğünü fark edip "neden burada?" diye sorgulayınca
ortaya çıktı.

**Nasıl çözüldü:** Tek-node "referansını" da AYNI `dagitik_ara()`
fonksiyonuna, sadece **tek elemanlı bir shard sözlüğüyle** vererek
oluşturdum. Böylece iki taraf da birebir aynı kod yolunu (aynı ayrıştırma,
aynı eşleştirme, aynı skorlama) kullanıyor — karşılaştırma gerçekten
elma-elma oldu.

**Genel ders:** Bir "referans/baseline" oluştururken, referansın da
test edilen sistemle **aynı iş mantığını** kullandığından emin olmak
gerekir — iki farklı kod yolunu karşılaştırmak, aralarındaki farkın
gerçek bir bug mu yoksa metodoloji farkı mı olduğunu belirsizleştirir.

## 4. İsim çakışması: paketin kendi alt-modülünü gölgelemesi (Faz 9)

**Ne oldu:** `shardsearch/api/__init__.py` içinde `from shardsearch.api.app
import app` satırı vardı — hem alt-modülün adı ("app.py") hem de ondan
export edilen değişkenin adı ("app", FastAPI nesnesi) aynıydı. Bu,
paketin `app` ATTRIBUTE'unu FastAPI nesnesiyle üzerine yazıyordu.
`pytest`'in `monkeypatch.setattr("shardsearch.api.app._fonksiyon", ...)`
string tabanlı çözümlemesi, dotted path'i attribute-zinciriyle takip
ederken modül yerine FastAPI nesnesini buluyor, `AttributeError:
'FastAPI' object has no attribute '_fonksiyon'` veriyordu.

**Nasıl bulundu:** Faz 9'un ilk test çalıştırmasında hata doğrudan
ortaya çıktı — traceback'te `obj = <FastAPI object>` görünce isim
çakışması şüphesi doğdu, `shardsearch/api/__init__.py`'ye bakınca
teyit edildi.

**Nasıl çözüldü:** `__init__.py`'yi boşalttım (re-export'u kaldırdım),
nedenini açıklayan bir yorum bıraktım ki gelecekte biri "yardımcı olayım"
diyip aynı satırı geri eklemesin.

**Genel ders:** Bir Python paketinde, bir alt-modülden export edilen
sembolün adı **alt-modülün kendi adıyla aynı olmamalı** — aksi halde
paket-seviyesi attribute erişimi (özellikle dotted-string ile dinamik
çözümleme yapan araçlar: pytest monkeypatch, `importlib`, bazı DI
container'ları) modül yerine export edilen değeri bulur.

## 5. Dağıtık sistemlerin klasik tuzağı: yerel IDF sapması (Faz 8)

Bu bir "hata" değil, **bilinçli kabul edilmiş bir yaklaşıklık** — ama
listeye dahil, çünkü ölçülüp kanıtlanmış olması onu diğerlerinden
ayırıyor. BM25'in IDF'i global korpus istatistiği gerektirir; her shard
sadece kendi belgelerine göre hesaplayınca (Elasticsearch'ün varsayılanı
ile aynı), sıralama tek-node'dan sapabiliyor. Dengeli dağıtımda küçük
(gözlemlendi), kasıtlı dengesiz dağıtımda 5 kattan büyük (gözlemlendi ve
ayrı bir testle kanıtlandı) bir sapma. Detaylar: `docs/faz-8-sonrasi-durum.md`.

**Genel ders:** Gerçek dağıtık sistemlerde "yaklaşık doğru ama hızlı"
kararlar (Elasticsearch'ün local IDF varsayılanı gibi) sıradandır —
önemli olan bu yaklaşıklığın büyüklüğünü ÖLÇEBİLMEK ve NE ZAMAN
büyüdüğünü açıklayabilmek, yok saymak değil.
