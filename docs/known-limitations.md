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
