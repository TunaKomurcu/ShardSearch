# ShardSearch

Sıfırdan, dağıtık çalışabilen bir metin arama motoru — **öğrenme projesi**.

Bu, üretime hazır bir Elasticsearch alternatifi değil. Amaç; ters indeks,
BM25 sıralama, consistent hashing ile sharding ve asyncio ile dağıtık
sorgu birleştirme gibi mekanizmaları hazır kütüphanelere sarılmadan,
kendi elimizle inşa ederek gerçekten anlamak.

- Proje kapsamı, kapsam dışı kararlar ve mimari için: [SPEC.md](SPEC.md)
- Faz faz yol haritası ve "definition of done" kriterleri için: [PHASES.md](PHASES.md)
- Depoda çalışırken uyulacak kurallar (yasak kısayollar dahil) için: [CLAUDE.md](CLAUDE.md)

## Durum

Şu an: **Faz 0 — Proje Kurulumu**

## Kurulum

Bağımlılık yönetimi [uv](https://github.com/astral-sh/uv) ile yapılıyor.

```bash
uv sync
uv run pytest
```
