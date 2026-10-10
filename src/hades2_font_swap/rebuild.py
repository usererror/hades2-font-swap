"""Render a replacement font into the Hades II sprite-font layout.

A rebuilt font keeps the original's character set, line spacing, baseline and cap
height, so text lands where the game's UI expects it. Only the glyph shapes and
horizontal metrics change. Characters the replacement font cannot draw (for example
Greek or Cyrillic in a Latin-only font) keep their original glyphs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from hades2_font_swap.xnb import Kerning, Rect, SpriteFont

ATLAS_GAP = 4
"""Empty pixels between glyphs in the atlas, so filtering never bleeds neighbours."""

EMPTY_GLYPH_WIDTH = 3
"""Atlas rectangle width the game's own files use for blank glyphs such as space."""

SIZING_CHARS = ("H", "A", "E")
"""Capitals used to match the replacement font's size to the original."""

_RENDER_PADDING = 4
_SIZE_SEARCH_STEPS = 30


class RebuildError(RuntimeError):
    """Raised when a font cannot be rebuilt with the chosen replacement."""


@dataclass(frozen=True)
class Glyph:
    """One rendered character, ready to be packed into an atlas."""

    image: Image.Image | None
    cropping: Rect
    kerning: Kerning


@dataclass(frozen=True)
class RebuildResult:
    """Outcome of :func:`rebuild_font`."""

    font: SpriteFont
    replaced: int
    small_caps: bool

    @property
    def total(self) -> int:
        """Number of glyphs in the rebuilt font."""
        return len(self.font.chars)


class ReplacementFont:
    """A TrueType/OpenType font that can be rendered at arbitrary pixel sizes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            with TTFont(path, fontNumber=0, lazy=True) as tt:
                cmap = tt.getBestCmap() or {}
        except Exception as exc:  # fontTools raises many exception types for bad files
            raise RebuildError(f"cannot read font {path}: {exc}") from exc
        self.codepoints = frozenset(cmap)

    def covers(self, char: str) -> bool:
        """Whether the font has a glyph for ``char``."""
        return len(char) == 1 and ord(char) in self.codepoints

    def at_size(self, pixels: float) -> ImageFont.FreeTypeFont:
        """Load the font at ``pixels`` pixels per em."""
        return ImageFont.truetype(str(self.path), pixels)

    def sized_to(self, char: str, target_height: int) -> ImageFont.FreeTypeFont:
        """Return the font sized so ``char``'s rendered ink is ``target_height`` pixels tall."""
        low, high = 2.0, 512.0
        for _ in range(_SIZE_SEARCH_STEPS):
            mid = (low + high) / 2
            image = render_glyph(self.at_size(mid), char, baseline=0, line_spacing=0).image
            if image is None or image.height < target_height:
                low = mid
            else:
                high = mid
        return self.at_size((low + high) / 2)


def render_glyph(
    font: ImageFont.FreeTypeFont, char: str, *, baseline: int, line_spacing: int
) -> Glyph:
    """Rasterise ``char`` and compute its metrics.

    ``baseline`` is the distance from the top of the line to the baseline. The glyph
    image is cropped to its ink, and its kerning width equals the image width, so it
    draws identically whether the engine positions glyphs by bearing or by image.
    """
    advance = font.getlength(char)
    x0, y0, x1, y1 = (int(v) for v in font.getbbox(char, anchor="ls"))
    if x1 > x0 and y1 > y0:
        pad = _RENDER_PADDING
        canvas = Image.new("L", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
        ImageDraw.Draw(canvas).text((pad - x0, pad - y0), char, font=font, fill=255, anchor="ls")
        ink = canvas.getbbox()
        if ink:
            image = canvas.crop(ink)
            left = x0 - pad + ink[0]
            top = y0 - pad + ink[1]
            return Glyph(
                image=image,
                cropping=Rect(0, baseline + top, int(advance), line_spacing),
                kerning=Kerning(float(left), float(image.width), advance - left - image.width),
            )
    return Glyph(
        image=None,
        cropping=Rect(0, baseline, int(advance), line_spacing),
        kerning=Kerning(0.0, 0.0, advance),
    )


def pack_atlas(
    images: Sequence[Image.Image | None], min_width: int
) -> tuple[Image.Image, list[Rect]]:
    """Shelf-pack glyph images into one Alpha8 atlas.

    Returns the atlas and each image's rectangle, in input order. The atlas is at least
    ``min_width`` wide (the game's original width) and its height is a multiple of 4.
    """
    sizes = [(im.width, im.height) if im else (EMPTY_GLYPH_WIDTH, 0) for im in images]
    width = max([min_width, *(w + 2 * ATLAS_GAP for w, _ in sizes)])
    order = sorted(range(len(images)), key=lambda i: -sizes[i][1])

    rects: dict[int, Rect] = {}
    x = y = ATLAS_GAP
    row_height = 0
    for i in order:
        w, h = sizes[i]
        if x + w + ATLAS_GAP > width:
            x, y, row_height = ATLAS_GAP, y + row_height + ATLAS_GAP, 0
        rects[i] = Rect(x, y, w, h)
        x += w + ATLAS_GAP
        row_height = max(row_height, h)

    height = y + row_height + ATLAS_GAP
    height += -height % 4
    atlas = Image.new("L", (width, height), 0)
    for i, image in enumerate(images):
        if image is not None:
            atlas.paste(image, (rects[i].x, rects[i].y))
    return atlas, [rects[i] for i in range(len(images))]


def build_font(
    chars: Sequence[str],
    glyphs: Sequence[Glyph],
    *,
    atlas_width: int,
    line_spacing: int,
    spacing: float,
    cap_height: int,
    default_char: str | None,
) -> SpriteFont:
    """Pack rendered glyphs into a complete :class:`SpriteFont`."""
    atlas, rects = pack_atlas([g.image for g in glyphs], atlas_width)
    return SpriteFont(
        width=atlas.width,
        height=atlas.height,
        pixels=atlas.tobytes(),
        glyphs=tuple(rects),
        cropping=tuple(g.cropping for g in glyphs),
        chars=tuple(chars),
        line_spacing=line_spacing,
        spacing=spacing,
        cap_height=cap_height,
        kerning=tuple(g.kerning for g in glyphs),
        default_char=default_char,
    )


def baseline_of(font: SpriteFont) -> int:
    """Distance from the top of a line to the baseline in an existing font."""
    space = font.index_of(" ")
    if space is not None and font.glyphs[space].height == 0:
        return font.cropping[space].y
    for char in SIZING_CHARS:
        i = font.index_of(char)
        if i is not None:
            return font.cropping[i].y + font.glyphs[i].height
    raise RebuildError("cannot find the baseline (no space or capital letters)")


def small_caps_height(font: SpriteFont) -> int | None:
    """If the font draws lowercase as small capitals, return their height in pixels.

    Small-caps fonts give ``k`` (which normally has an ascender) the same height as
    ``x``, and both are shorter than ``X``.
    """
    heights = {}
    for char in "kxX":
        i = font.index_of(char)
        if i is None:
            return None
        heights[char] = font.glyphs[i].height
    if heights["k"] and abs(heights["k"] - heights["x"]) <= 1 and heights["x"] < heights["X"]:
        return heights["x"]
    return None


def _original_glyph(font: SpriteFont, atlas: Image.Image, i: int) -> Glyph:
    r = font.glyphs[i]
    image = atlas.crop((r.x, r.y, r.x + r.width, r.y + r.height)) if r.width and r.height else None
    return Glyph(image=image, cropping=font.cropping[i], kerning=font.kerning[i])


def rebuild_font(original: SpriteFont, replacement: ReplacementFont) -> RebuildResult:
    """Redraw ``original`` using ``replacement``, keeping its layout metrics."""
    sizing_char = next(
        (c for c in SIZING_CHARS if original.index_of(c) is not None and replacement.covers(c)),
        None,
    )
    if sizing_char is None:
        raise RebuildError("the replacement font has none of the capitals used for sizing")
    target = original.glyphs[original.chars.index(sizing_char)].height
    regular = replacement.sized_to(sizing_char, target)

    sc_height = small_caps_height(original)
    small = replacement.sized_to("X", sc_height) if sc_height and replacement.covers("X") else None

    baseline = baseline_of(original)
    atlas = Image.frombytes("L", (original.width, original.height), original.pixels)

    glyphs: list[Glyph] = []
    replaced = 0
    for i, char in enumerate(original.chars):
        font, source = regular, char
        upper = char.upper()
        if small is not None and char.islower() and replacement.covers(upper):
            font, source = small, upper
        if replacement.covers(source):
            glyphs.append(
                render_glyph(font, source, baseline=baseline, line_spacing=original.line_spacing)
            )
            replaced += 1
        else:
            glyphs.append(_original_glyph(original, atlas, i))

    rebuilt = build_font(
        original.chars,
        glyphs,
        atlas_width=original.width,
        line_spacing=original.line_spacing,
        spacing=original.spacing,
        cap_height=original.cap_height,
        default_char=original.default_char,
    )
    return RebuildResult(font=rebuilt, replaced=replaced, small_caps=small is not None)
