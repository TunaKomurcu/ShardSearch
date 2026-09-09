# Bilerek boş: `app`'ı burada `shardsearch.api.app`'tan tekrar export
# etmeyin. Alt-modülün adı da "app" olduğu için, `from shardsearch.api.app
# import app` bu paketin `app` ATTRIBUTE'unu (FastAPI nesnesi) alt-modülün
# kendisinin üzerine yazar — dotted-path attribute çözümlemesi (ör.
# pytest'in monkeypatch.setattr(str) tarafı) o zaman modül yerine FastAPI
# nesnesini bulur. `from shardsearch.api.app import app` her zaman
# doğrudan alt-modülden import edin.
