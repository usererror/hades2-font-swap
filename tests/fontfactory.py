"""Build synthetic Hades II font files from openly licensed fonts.

The real game files can't be committed (they contain commercial fonts), so tests
generate look-alikes: same layout, same conventions, DejaVu glyphs.
"""

from __future__ import annotations

from pathlib import Path

from hades2_font_swap import xnb
from hades2_font_swap.rebuild import ReplacementFont, build_font, render_glyph

FIXTURES = Path(__file__).parent / "fixtures"
ORIGINAL_FONT = FIXTURES / "DejaVuSans-LatinCyrillic.ttf"
"""Stands in for the game's own fonts. Covers Latin and Cyrillic."""
REPLACEMENT_FONT = FIXTURES / "DejaVuSerif-Latin.ttf"
"""Stands in for the user's font. Latin only, to exercise the fallback path."""

CHARS = tuple(
    sorted(
        {chr(c) for c in range(0x20, 0x7F)}
        | set("\xa0éÉöÖß")
        | set("\u041f\u0440\u0438\u0432\u0435\u0442"),  # Cyrillic, absent from the replacement
        key=ord,
    )
)
LINE_SPACING = 40
BASELINE = 32


def make_game_font(*, size: float = 30.0, small_caps: bool = False) -> xnb.SpriteFont:
    """A font laid out the way the game's files are."""
    source = ReplacementFont(ORIGINAL_FONT)
    regular = source.at_size(size)
    small = source.at_size(size * 0.75)
    glyphs = []
    for char in CHARS:
        font, drawn = regular, char
        if small_caps and char.islower() and source.covers(char.upper()):
            font, drawn = small, char.upper()
        glyphs.append(render_glyph(font, drawn, baseline=BASELINE, line_spacing=LINE_SPACING))
    cap = glyphs[CHARS.index("H")].image
    assert cap is not None
    return build_font(
        CHARS,
        glyphs,
        atlas_width=256,
        line_spacing=LINE_SPACING,
        spacing=0.0,
        cap_height=cap.height,
        default_char="*",
    )


def make_game_dir(root: Path) -> Path:
    """Create a fake Hades II install with a few representative font files."""
    game = root / "Hades II"
    fonts = game / "Content" / "Fonts" / "bin" / "en"
    fonts.mkdir(parents=True)
    regular = xnb.dumps(make_game_font())
    (fonts / "LatoBold.xnb").write_bytes(regular)
    (fonts / "LatoBold64.xnb").write_bytes(xnb.dumps(make_game_font(size=60.0)))
    (fonts / "P22UndergroundSCMedium.xnb").write_bytes(xnb.dumps(make_game_font(small_caps=True)))
    (fonts / "MonospaceTypewriterBold.xnb").write_bytes(regular)
    (fonts / "ja.xnb").write_bytes(regular)
    return game
