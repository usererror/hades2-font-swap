from __future__ import annotations

import struct
from dataclasses import replace

import pytest

from hades2_font_swap import xnb


def test_round_trip_is_byte_identical(game_font: xnb.SpriteFont) -> None:
    data = xnb.dumps(game_font)
    assert xnb.dumps(xnb.loads(data)) == data
    assert xnb.loads(data) == game_font


def test_header(game_font: xnb.SpriteFont) -> None:
    data = xnb.dumps(game_font)
    assert data[:6] == xnb.MAGIC
    assert struct.unpack_from("<I", data, 6)[0] == len(data)
    surface, width, height, mips, size = struct.unpack_from("<iiiiI", data, 10)
    assert (surface, mips) == (xnb.SURFACE_ALPHA8, 1)
    assert size == width * height == len(game_font.pixels)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 337, 16_383, 16_384, 2**21])
def test_varint_round_trip(value: int) -> None:
    encoded = xnb._write_varint(value)
    reader = xnb._Reader(encoded)
    assert reader.varint() == value
    assert reader.pos == len(encoded)


def test_varint_matches_dotnet_encoding() -> None:
    # 337 glyphs is what LatoBold.xnb stores: bytes D1 02.
    assert xnb._write_varint(337) == b"\xd1\x02"


def test_multibyte_chars_survive(game_font: xnb.SpriteFont) -> None:
    font = xnb.loads(xnb.dumps(game_font))
    assert "\u041f" in font.chars  # Cyrillic Pe, a 2-byte UTF-8 char
    assert "é" in font.chars


def test_rejects_wrong_magic(game_font: xnb.SpriteFont) -> None:
    data = bytearray(xnb.dumps(game_font))
    data[4] = 5  # XNA's standard version 5
    with pytest.raises(xnb.XnbFormatError, match="not a Hades II font"):
        xnb.loads(bytes(data))


def test_rejects_truncated_file(game_font: xnb.SpriteFont) -> None:
    data = xnb.dumps(game_font)
    truncated = data[:-10]
    truncated = truncated[:6] + struct.pack("<I", len(truncated)) + truncated[10:]
    with pytest.raises(xnb.XnbFormatError, match="unexpected end"):
        xnb.loads(truncated)


def test_rejects_size_mismatch(game_font: xnb.SpriteFont) -> None:
    with pytest.raises(xnb.XnbFormatError, match="header says"):
        xnb.loads(xnb.dumps(game_font) + b"\x00")


def test_rejects_trailing_bytes(game_font: xnb.SpriteFont) -> None:
    data = xnb.dumps(game_font) + b"\x00\x00"
    data = data[:6] + struct.pack("<I", len(data)) + data[10:]
    with pytest.raises(xnb.XnbFormatError, match="trailing"):
        xnb.loads(data)


def test_inconsistent_font_is_rejected(game_font: xnb.SpriteFont) -> None:
    with pytest.raises(xnb.XnbFormatError, match="counts differ"):
        replace(game_font, chars=game_font.chars[:-1])
    with pytest.raises(xnb.XnbFormatError, match="atlas size"):
        replace(game_font, pixels=b"")


def test_no_default_char(game_font: xnb.SpriteFont) -> None:
    font = replace(game_font, default_char=None)
    assert xnb.loads(xnb.dumps(font)).default_char is None


def test_kerning_advance() -> None:
    assert xnb.Kerning(1.0, 10.0, 2.0).advance == 13.0
