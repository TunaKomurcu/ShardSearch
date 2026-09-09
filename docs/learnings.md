# Öğrenmeler: ShardSearch, Faz 0'dan Buraya

Bu, projenin kapanış dokümanı — Faz 0'dan (proje iskeleti) Faz 10'a
(gözlemlenebilirlik + yük testi, PHASES.md'nin son planlı fazı) kadar
geçen yolculuğun özeti ve genel dersi. `docs/yolculuk-ozeti.md` "hangi
hatalar bulundu, nasıl çözüldü"ye odaklanıyordu; bu doküman bir adım
geri çekilip **neden bu hataların "kara kutu kullansaydık" görünmez
kalacağını** ele alıyor — projenin asıl amacı buydu.

## Ne yapıldı (özet)

11 faz planlandı, 10'u (0-10) tamamlandı — Faz 11 (Zemberek, hibrit
vektör arama, Docker) SPEC.md'de zaten opsiyonel/stretch olarak
işaretliydi, bilinçli olarak atlandı (düşük öğrenme kaldıracı, hibrit
arama zaten mevcut iş tecrübesinde vardı). SPEC.md'nin iki büyük başarı
kriteri de karşılandı:

- **Faz 6 sonu:** gerçek bir HTTP isteğiyle uçtan uca, tek-node arama çalışıyor.
- **Faz 8 sonu:** 3 shard'a dağıtılmış veri üzerinde, tek-node sonuçlarıyla
  tutarlı (açıklanabilir farklarla) dağıtık arama çalışıyor.

Detaylı faz-faz özet: `docs/mvp-ozet.md` (Faz 0-6) ve
`docs/faz-8-sonrasi-durum.md` (Faz 7-8).

## Bulunan gerçek hatalar (özet — detaylar docs/yolculuk-ozeti.md'de)

1. **Faz branch'ini açmayı unutmak** (Faz 2) — süreç disiplini, `git
   reset --hard` + branch taşımayla düzeltildi.
2. **Tanımsız tie-break** (Faz 3) — eşit BM25 skorlu belgelerin sırası
   bir `set`'in hash sırasına bağlıydı; `(-skor, belge_id)` ikincil
   anahtarıyla deterministik hale getirildi.
3. **Elma-armut test karşılaştırması** (Faz 8) — dağıtık aramayı Faz 5'in
   boolean parser'ını hiç bilmeyen eski bir fonksiyonla karşılaştırıyordum;
   tek-node referansını da aynı `dagitik_ara()`'ya (tek shard'la) vererek
   düzeltildi.
4. **Paketin kendi alt-modülünü gölgelemesi** (Faz 9) — `__init__.py`'de
   alt-modülle aynı isimde bir export, dotted-path attribute çözümlemesini
   (pytest monkeypatch dahil) bozuyordu.
5. **Dağıtık yerel IDF sapması** (Faz 8) — bilinçli bir yaklaşıklık,
   ölçülüp büyüklüğü kanıtlandı (dengeli dağıtımda küçük, dengesizde 5
   kattan büyük).
6. **Event loop'u bloke eden gizli senkron çağrı** (Faz 10) — `async def`
   bir route'un içinde senkron Redis çağrıları, tüm event loop'u
   durduruyordu; gerçek Locust yük testi olmasa asla görünmezdi.

## "Kara kutu kullanmak" ile "sıfırdan inşa etmek" arasındaki fark, somut örneklerle

Projenin başındaki amaç şuydu: *"çalışıyor" (hata vermiyor) ile "doğru
çalışıyor" (neden doğru çalıştığını bilmek) arasındaki farkı yaşamak.*
Her fazda bu fark farklı bir şekilde somutlaştı:

**Tokenizer (Faz 1):** Bir kütüphane kullansaydık `.lower()` çağırıp
geçerdik. Sıfırdan yazınca, Python'un `str.lower()`'ının Türkçe'de
`'I'` → `'i'` yaptığını (doğrusu `'ı'`) ve `'İ'` → `'i̇'` (birleşik
karakter) ürettiğini fark etmek zorunda kaldık — bu, Unicode'un
"küçültme" kavramının dile göre değiştiğini somut olarak öğretti.

**Ters indeks (Faz 2):** Bir arama kütüphanesi bunu bizden gizlerdi.
Sıfırdan yazınca, postings listesinin SIRALI tutulmasının (Faz 5/8'in
kesişim/birleştirme algoritmalarının O(n) çalışabilmesi için) baştan
tasarım kararı olması gerektiğini gördük — sona bırakılan bir "sort"
değil.

**BM25 (Faz 3):** `rank_bm25 import BM25Okapi` yazıp geçebilirdik. Kendi
yazınca, IDF formülünün klasik hâlinin (Robertson-Sparck Jones)
NEGATİF çıkabildiğini, gerçek kütüphanelerin bunu bir epsilon ile
yamaladığını ve bizim bunun yerine formülün pozitif garanti eden bir
varyantını seçebileceğimizi (ve bu seçimin SIRALAMA testlerini nasıl
etkilediğini) doğrudan yaşadık.

**SQLite depolama (Faz 4):** Bir ORM kullansaydık index'leri o yönetirdi.
Sıfırdan şema tasarlayınca, `(token, belge_id)` birincil anahtarının
SADECE token'la başlayan aramalarda işe yaradığını, `belge_id` tek
başına arandığında (upsert silme) AYRI bir index gerektiğini —
bellek-içi versiyondaki Python dict'in SQL karşılığının bu olduğunu —
görmek zorunda kaldık.

**Sorgu ayrıştırıcı (Faz 5):** Bir regex ya da hazır parser kullansaydık
operatör önceliği "bir yerlerde" gizli kalırdı. Recursive-descent
gramerini elle yazınca, `AND`'in `OR`'dan sıkı bağlanmasının bir "kural"
değil, gramerin YAPISININ (veya → ve → terim) doğal bir SONUCU olduğunu
gördük — ayrı bir öncelik tablosuna hiç gerek kalmadı.

**Sharding (Faz 7):** `hash(id) % N` yazıp geçebilirdik. Consistent
hashing'i elle kurunca, NEDEN sanal düğümlere ihtiyaç olduğunu (dağılım
varyansı ölçülerek KANITLANDI, sadece iddia edilmedi) ve resharding'in
NEDEN sadece eski→yeni geçişe izin verip eski→eski'ye izin vermediğini
(test edilerek doğrulandı) somut olarak gördük.

**Dağıtık sorgu (Faz 8):** Elasticsearch kullansaydık "local IDF
kullanıyor" diye bir dokümantasyon satırı okurduk, inanırdık. Kendi
yazınca, bu yaklaşıklığın BÜYÜKLÜĞÜNÜ kendi ellerimizle ölçüp (dengeli
dağıtımda küçük, kasıtlı dengesizde 5 kat) kanıtladık.

**Cache (Faz 9):** "Cache invalidation, bilgisayar bilimindeki iki zor
problemden biri" sözünü okumuştuk. Kendi cache-aside'ımızı yazınca, BU
SİSTEM İÇİN "seçici invalidation imkansız çünkü BM25 istatistikleri
global" gerçeğiyle yüzleşip kuşak-sayacı çözümüne KENDİMİZ ulaştık —
bir kütüphane bu kararı bizim yerimize verip gizlemezdi.

**Gözlemlenebilirlik + yük testi (Faz 10) — en derin ders:** Eğer FastAPI'yi
"kara kutu" olarak kullanıp `async def` yazmanın kendiliğinden yeterli
olduğunu varsaysaydık, bu proje asla bitmiş "çalışan" bir üründen farklı
görünmezdi — testler geçerdi, curl ile tek istekler hızlı dönerdi. Sadece
GERÇEK, EŞZAMANLI bir yük testi (ve threading.Lock gibi "makul" bir ilk
şüpheliyi izole testle elemeye istekli olmak) `async def`'in içindeki
senkron bir çağrının tüm event loop'u durdurduğunu ortaya çıkardı. Bu,
"anlaşıldığını düşünmek" ile "gerçekten anlamak" arasındaki farkın en
net kanıtıydı — ve tam olarak SPEC.md'nin baştan beri peşinde olduğu şey.

## Kapanış

Bu proje "üretime hazır bir Elasticsearch alternatifi" olmayı hiç
hedeflemedi (SPEC.md, satır 5). Hedef, arama motorlarının mekanizmalarını
gerçekten anlayarak inşa etmekti. Bulunan 6 gerçek şeyin 5'i düzeltilmiş
hatalardı (git branch, tie-break, elma-armut karşılaştırma, `__init__.py`
gölgelenmesi, event loop bloklanması); 1'i (yerel IDF sapması) bilinçli
kabul edilmiş ve ÖLÇÜLMÜŞ bir yaklaşıklıktı. Hiçbiri "çalışıyor, o zaman
doğrudur" varsayımıyla bırakılmadı.
