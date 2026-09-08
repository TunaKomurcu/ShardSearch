# Referans Korpus — Nasıl Elde Edilir

SPEC.md'de belirtildiği gibi, doğrulama ve göz-kararı değerlendirme için
sentetik değil **gerçek bir Türkçe metin korpusu** kullanılacak: Türkçe
Wikipedia'dan alınmış 200-500 makale.

`data/corpus/` klasörü `.gitignore` içinde — bu veri repoya commit edilmez,
her geliştirici kendi makinesinde aşağıdaki adımlarla oluşturur.

## Yöntem (Faz 2/3'te uygulanacak)

1. Türkçe Wikipedia dump'ından (`trwiki-latest-pages-articles.xml.bz2`,
   https://dumps.wikimedia.org/trwiki/latest/) rastgele 200-500 makale seç.
2. `wikiextractor` (veya benzeri) ile düz metne çevir.
3. Her makaleyi `data/corpus/<belge_id>.txt` olarak kaydet — bir dosya bir belge.
4. Kaynak/lisans notu: Wikipedia içeriği CC BY-SA 4.0 lisanslıdır, sadece
   yerel geliştirme/test amaçlı kullanılır, repoya dahil edilmez.

Bu adımlar Faz 2 (Ters İndeks) ve Faz 3 (BM25 doğrulama) sırasında,
korpus gerçekten kullanılmaya başlandığında bir script (`scripts/fetch_corpus.py`
gibi) ile otomatize edilecek. Faz 0'da sadece klasör iskeleti hazır.
