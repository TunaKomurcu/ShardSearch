# Deliberately empty: do not re-export `app` from `shardsearch.api.app`
# here. Since the submodule is also named "app", `from shardsearch.api.app
# import app` would overwrite this package's `app` ATTRIBUTE (the FastAPI
# object) on top of the submodule itself — dotted-path attribute
# resolution (e.g. pytest's monkeypatch.setattr(str)) would then find the
# FastAPI object instead of the module. Always
# `from shardsearch.api.app import app` directly from the submodule.
