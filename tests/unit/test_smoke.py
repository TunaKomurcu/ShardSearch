"""Phase 0 sanity check: the project skeleton is set up and pytest runs.

Real tests start from Phase 1 onward (tokenizer, inverted index, etc.).
"""

import shardsearch


def test_package_is_importable() -> None:
    assert shardsearch is not None
