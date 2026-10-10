"""Checks against real Hades II files. Skipped unless HADES2_FONTS_DIR is set.

The game's files can't be committed, so point this at your own install, e.g.:
    HADES2_FONTS_DIR="C:/Program Files (x86)/Steam/steamapps/common/Hades II/Content/Fonts/bin/en"
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hades2_font_swap import xnb
from hades2_font_swap.rebuild import ReplacementFont, rebuild_font

_DIR = os.environ.get("HADES2_FONTS_DIR")
_FILES = sorted(Path(_DIR).glob("*.xnb")) if _DIR else []

pytestmark = pytest.mark.skipif(not _FILES, reason="set HADES2_FONTS_DIR to run")


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_real_file_round_trips(path: Path) -> None:
    data = path.read_bytes()
    assert xnb.dumps(xnb.loads(data)) == data


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_real_file_rebuilds(path: Path, replacement: ReplacementFont) -> None:
    original = xnb.load(path)
    if not any(original.index_of(c) is not None for c in "HAE"):
        pytest.skip("no Latin capitals (CJK or language-name font)")
    new = rebuild_font(original, replacement).font
    assert new.chars == original.chars
    assert xnb.loads(xnb.dumps(new)) == new
