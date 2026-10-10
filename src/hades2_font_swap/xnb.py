"""Read and write Hades II font files (``Content/Fonts/bin/<lang>/*.xnb``).

The layout is documented in ``docs/FORMAT.md``. In short, it is XNA's ``SpriteFont``
with the type-reader table removed, the version bumped to 6, and one extra integer
(the cap height) added after the spacing field.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"XNBw\x06\x00"
"""``XNB`` + target platform ``w`` (Windows) + version 6 + flags 0 (uncompressed)."""

SURFACE_ALPHA8 = 12
"""XNA ``SurfaceFormat.Alpha8``: one byte of coverage per pixel."""

_HEADER = struct.Struct("<6sI")
_TEXTURE = struct.Struct("<iiiiI")
_RECT = struct.Struct("<iiii")
_VEC3 = struct.Struct("<fff")
_METRICS = struct.Struct("<ifi")


class XnbFormatError(ValueError):
    """Raised when a file does not match the Hades II font layout."""


@dataclass(frozen=True)
class Rect:
    """An integer rectangle (XNA ``Rectangle``)."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Kerning:
    """Per-glyph horizontal metrics (XNA's ``Vector3`` kerning entry), in pixels."""

    left: float
    width: float
    right: float

    @property
    def advance(self) -> float:
        """Total horizontal pen movement for this glyph."""
        return self.left + self.width + self.right


@dataclass(frozen=True)
class SpriteFont:
    """A decoded Hades II font: an alpha atlas plus per-glyph metrics.

    Attributes:
        width: Atlas width in pixels.
        height: Atlas height in pixels.
        pixels: Row-major Alpha8 atlas data, ``width * height`` bytes.
        glyphs: Each glyph's rectangle inside the atlas.
        cropping: Each glyph's placement in its line cell. ``y`` is the offset of the
            glyph's top from the top of the line; ``width`` is the advance and
            ``height`` the line spacing.
        chars: The character each glyph represents, sorted by code point.
        line_spacing: Distance between baselines, in pixels.
        spacing: Extra space added after every glyph.
        cap_height: Height of capital letters, in pixels.
        kerning: Horizontal metrics for each glyph.
        default_char: Character drawn for anything missing from ``chars``.
    """

    width: int
    height: int
    pixels: bytes
    glyphs: tuple[Rect, ...]
    cropping: tuple[Rect, ...]
    chars: tuple[str, ...]
    line_spacing: int
    spacing: float
    cap_height: int
    kerning: tuple[Kerning, ...]
    default_char: str | None

    def __post_init__(self) -> None:
        n = len(self.chars)
        if not len(self.glyphs) == len(self.cropping) == len(self.kerning) == n:
            raise XnbFormatError("glyph, cropping, kerning and char counts differ")
        if len(self.pixels) != self.width * self.height:
            raise XnbFormatError("pixel data does not match atlas size")

    def index_of(self, char: str) -> int | None:
        """Return the glyph index for ``char``, or ``None`` if the font lacks it."""
        try:
            return self.chars.index(char)
        except ValueError:
            return None


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        end = self.pos + size
        if end > len(self.data):
            raise XnbFormatError("unexpected end of file")
        chunk = self.data[self.pos : end]
        self.pos = end
        return chunk

    def varint(self) -> int:
        """Read a 7-bit encoded integer (.NET ``BinaryReader.Read7BitEncodedInt``)."""
        result = shift = 0
        while True:
            byte = self.take(1)[0]
            result |= (byte & 0x7F) << shift
            shift += 7
            if byte < 0x80:
                return result

    def char(self) -> str:
        lead = self.data[self.pos] if self.pos < len(self.data) else 0
        size = 1 if lead < 0x80 else 2 if lead < 0xE0 else 3 if lead < 0xF0 else 4
        return self.take(size).decode("utf-8")

    def rects(self) -> tuple[Rect, ...]:
        return tuple(Rect(*_RECT.unpack(self.take(_RECT.size))) for _ in range(self.varint()))


def _write_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def loads(data: bytes) -> SpriteFont:
    """Decode a Hades II font file from bytes."""
    r = _Reader(data)
    magic, size = _HEADER.unpack(r.take(_HEADER.size))
    if magic != MAGIC:
        raise XnbFormatError(f"not a Hades II font file (header {magic!r})")
    if size != len(data):
        raise XnbFormatError(f"header says {size} bytes, file has {len(data)}")

    surface, width, height, mips, pixel_bytes = _TEXTURE.unpack(r.take(_TEXTURE.size))
    if surface != SURFACE_ALPHA8 or mips != 1:
        raise XnbFormatError(f"unsupported texture (format {surface}, {mips} mip levels)")
    pixels = r.take(pixel_bytes)

    glyphs = r.rects()
    cropping = r.rects()
    chars = tuple(r.char() for _ in range(r.varint()))
    line_spacing, spacing, cap_height = _METRICS.unpack(r.take(_METRICS.size))
    kerning = tuple(Kerning(*_VEC3.unpack(r.take(_VEC3.size))) for _ in range(r.varint()))
    default_char = r.char() if r.take(1)[0] else None

    if r.pos != len(data):
        raise XnbFormatError(f"{len(data) - r.pos} unexpected trailing bytes")

    return SpriteFont(
        width=width,
        height=height,
        pixels=pixels,
        glyphs=glyphs,
        cropping=cropping,
        chars=chars,
        line_spacing=line_spacing,
        spacing=spacing,
        cap_height=cap_height,
        kerning=kerning,
        default_char=default_char,
    )


def dumps(font: SpriteFont) -> bytes:
    """Encode a font back to the Hades II file layout."""
    body = bytearray(_TEXTURE.pack(SURFACE_ALPHA8, font.width, font.height, 1, len(font.pixels)))
    body += font.pixels
    for rects in (font.glyphs, font.cropping):
        body += _write_varint(len(rects))
        for rect in rects:
            body += _RECT.pack(rect.x, rect.y, rect.width, rect.height)
    body += _write_varint(len(font.chars))
    for char in font.chars:
        body += char.encode("utf-8")
    body += _METRICS.pack(font.line_spacing, font.spacing, font.cap_height)
    body += _write_varint(len(font.kerning))
    for k in font.kerning:
        body += _VEC3.pack(k.left, k.width, k.right)
    body += b"\x00" if font.default_char is None else b"\x01" + font.default_char.encode("utf-8")
    return _HEADER.pack(MAGIC, _HEADER.size + len(body)) + bytes(body)


def load(path: Path) -> SpriteFont:
    """Read a Hades II font file from disk."""
    try:
        return loads(path.read_bytes())
    except XnbFormatError as exc:
        raise XnbFormatError(f"{path.name}: {exc}") from exc


def dump(font: SpriteFont, path: Path) -> None:
    """Write a font to disk."""
    path.write_bytes(dumps(font))
