# Reference Corpus — How to Obtain It

As noted in SPEC.md, a real **Turkish text corpus** is used for
validation and eyeballed relevance checks rather than synthetic data:
200-500 articles from Turkish Wikipedia.

`data/corpus/` is listed in `.gitignore` — this data is not committed to
the repo; each developer generates it locally following the steps below.

## Method

1. Pick 200-500 random articles from a Turkish Wikipedia dump
   (`trwiki-latest-pages-articles.xml.bz2`,
   https://dumps.wikimedia.org/trwiki/latest/).
2. Convert to plain text with `wikiextractor` (or similar).
3. Save each article as `data/corpus/<doc_id>.txt` — one file per document.
4. Source/license note: Wikipedia content is licensed CC BY-SA 4.0, used
   here only for local development/testing, and not included in the repo.

These steps can be automated with a script (e.g.
`scripts/fetch_corpus.py`) once the corpus is actually put to use.
