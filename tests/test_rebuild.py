from __future__ import annotations

from itertools import combinations

from PIL import Image

from hades2_font_swap import xnb
from hades2_font_swap.rebuild import (
    ATLAS_GAP,
    ReplacementFont,
    baseline_of,
    pack_atlas,
    rebuild_font,
    small_caps_height,
)

CYRILLIC_PE = "\u041f"


def _glyph_pixels(font: xnb.SpriteFont, char: str) -> bytes:
    atlas = Image.frombytes("L", (font.width, font.height), font.pixels)
    r = font.glyphs[font.chars.index(char)]
    return atlas.crop((r.x, r.y, r.x + r.width, r.y + r.height)).tobytes()


def test_layout_metrics_are_preserved(
    game_font: xnb.SpriteFont, replacement: ReplacementFont
) -> None:
    new = rebuild_font(game_font, replacement).font
    assert new.chars == game_font.chars
    assert new.line_spacing == game_font.line_spacing
    assert new.cap_height == game_font.cap_height
    assert new.spacing == game_font.spacing
    assert new.default_char == game_font.default_char
    assert xnb.loads(xnb.dumps(new)) == new


def test_capitals_keep_their_height(
    game_font: xnb.SpriteFont, replacement: ReplacementFont
) -> None:
    new = rebuild_font(game_font, replacement).font
    i = game_font.chars.index("H")
    assert abs(new.glyphs[i].height - game_font.glyphs[i].height) <= 1


def test_baseline_is_preserved(game_font: xnb.SpriteFont, replacement: ReplacementFont) -> None:
    new = rebuild_font(game_font, replacement).font
    assert abs(baseline_of(new) - baseline_of(game_font)) <= 1
    i = new.chars.index("H")
    assert abs(new.cropping[i].y + new.glyphs[i].height - baseline_of(game_font)) <= 1


def test_glyphs_change_shape(game_font: xnb.SpriteFont, replacement: ReplacementFont) -> None:
    new = rebuild_font(game_font, replacement).font
    assert _glyph_pixels(new, "g") != _glyph_pixels(game_font, "g")


def test_missing_characters_keep_original_glyph(
    game_font: xnb.SpriteFont, replacement: ReplacementFont
) -> None:
    result = rebuild_font(game_font, replacement)
    new = result.font
    i = game_font.chars.index(CYRILLIC_PE)
    assert not replacement.covers(CYRILLIC_PE)
    assert new.kerning[i] == game_font.kerning[i]
    assert new.cropping[i] == game_font.cropping[i]
    assert _glyph_pixels(new, CYRILLIC_PE) == _glyph_pixels(game_font, CYRILLIC_PE)
    cyrillic = sum(1 for c in game_font.chars if not replacement.covers(c))
    assert result.replaced == result.total - cyrillic


def test_replaced_glyph_width_matches_image(
    game_font: xnb.SpriteFont, replacement: ReplacementFont
) -> None:
    new = rebuild_font(game_font, replacement).font
    for i, char in enumerate(new.chars):
        if replacement.covers(char) and new.glyphs[i].height:
            assert new.kerning[i].width == new.glyphs[i].width


def test_blank_glyphs(game_font: xnb.SpriteFont, replacement: ReplacementFont) -> None:
    new = rebuild_font(game_font, replacement).font
    i = new.chars.index(" ")
    assert new.glyphs[i].height == 0
    assert new.kerning[i].left == new.kerning[i].width == 0.0
    assert new.kerning[i].right > 0


def test_small_caps_detection(
    game_font: xnb.SpriteFont, small_caps_font: xnb.SpriteFont, replacement: ReplacementFont
) -> None:
    assert small_caps_height(game_font) is None
    assert small_caps_height(small_caps_font) is not None
    assert not rebuild_font(game_font, replacement).small_caps

    result = rebuild_font(small_caps_font, replacement)
    assert result.small_caps
    new = result.font
    lower_k = new.glyphs[new.chars.index("k")].height
    lower_x = new.glyphs[new.chars.index("x")].height
    upper_x = new.glyphs[new.chars.index("X")].height
    assert abs(lower_k - lower_x) <= 1
    assert lower_x < upper_x


def test_atlas_packing_has_no_overlaps() -> None:
    images: list[Image.Image | None] = [
        Image.new("L", (w, h), 255) for w, h in [(10, 20), (30, 5), (50, 40), (7, 7)] * 10
    ]
    images.append(None)
    atlas, rects = pack_atlas(images, min_width=64)
    assert atlas.width >= 64
    assert atlas.height % 4 == 0
    for r in rects:
        assert r.x >= ATLAS_GAP
        assert r.y >= ATLAS_GAP
        assert r.x + r.width <= atlas.width
        assert r.y + r.height <= atlas.height
    boxes = [r for r in rects if r.height]
    for a, b in combinations(boxes, 2):
        assert (
            a.x + a.width <= b.x
            or b.x + b.width <= a.x
            or a.y + a.height <= b.y
            or b.y + b.height <= a.y
        )


def test_atlas_grows_for_wide_glyphs() -> None:
    atlas, _ = pack_atlas([Image.new("L", (300, 10), 255)], min_width=64)
    assert atlas.width >= 300 + 2 * ATLAS_GAP
