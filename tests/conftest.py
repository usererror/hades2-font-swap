from __future__ import annotations

from pathlib import Path

import pytest

from fontfactory import REPLACEMENT_FONT, make_game_dir, make_game_font
from hades2_font_swap import xnb
from hades2_font_swap.rebuild import ReplacementFont


@pytest.fixture(scope="session")
def game_font() -> xnb.SpriteFont:
    return make_game_font()


@pytest.fixture(scope="session")
def small_caps_font() -> xnb.SpriteFont:
    return make_game_font(small_caps=True)


@pytest.fixture(scope="session")
def replacement() -> ReplacementFont:
    return ReplacementFont(REPLACEMENT_FONT)


@pytest.fixture
def game_dir(tmp_path: Path) -> Path:
    return make_game_dir(tmp_path)


@pytest.fixture
def fonts_dir(game_dir: Path) -> Path:
    return game_dir / "Content" / "Fonts" / "bin" / "en"
