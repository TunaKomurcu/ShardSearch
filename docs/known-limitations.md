# Bilinen Sınırlamalar

- **Tireli birleşik kelimeler (Faz 1 tokenizer):** `tokenize()` apostrof
  dışındaki tüm harf-olmayan karakterleri sessizce atıyor, split noktası
  olarak kullanmıyor. Bu yüzden `"anayasa-mahkemesi"` gibi tireli kelimeler
  `"anayasamahkemesi"` şeklinde tek token'a düşüyor. Şimdilik bilinçli
  olarak ertelendi — Faz 2'de gerçek Wikipedia korpusuyla karşılaşınca ne
  sıklıkla sorun çıkardığına bakıp karar verilecek.
