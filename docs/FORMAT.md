# Hades II font file format

Hades II stores its fonts as pre-rendered bitmap atlases in
`Content/Fonts/bin/<language>/*.xnb`. The container is a variant of Microsoft XNA's
compiled `SpriteFont`. This document describes the layout as reverse-engineered for
this project.

The description was verified by reading and re-writing shipped game files
(`LatoBold.xnb`, `CaesarDressing.xnb`): the output is byte-for-byte identical to the
input. You can repeat that check against your own install with:

```sh
HADES2_FONTS_DIR="/path/to/Hades II/Content/Fonts/bin/en" uv run pytest tests/test_real_game_files.py
```

## Differences from standard XNA 4.0

| Standard XNA `SpriteFont` (version 5)            | Hades II (version 6)             |
| ------------------------------------------------ | -------------------------------- |
| Type-reader table (`SpriteFontReader`, etc.)     | Absent                           |
| Shared-resource count and type indices           | Absent                           |
| Version byte `5`                                 | `6`                              |
| `LineSpacing`, `Spacing`                         | `LineSpacing`, `Spacing`, **`CapHeight`** |

Tools that produce standard XNA fonts (MonoGame's content pipeline, XNA Game Studio)
can't produce these files directly.

## Layout

All integers are little-endian. `varint` is .NET's 7-bit encoded integer
(`BinaryReader.Read7BitEncodedInt`): 7 bits per byte, high bit set on every byte
except the last. `char` is a single UTF-8 encoded character (1 to 4 bytes).

### Header

| Offset | Type      | Value / meaning                                  |
| ------ | --------- | ------------------------------------------------ |
| 0      | 3 bytes   | `XNB`                                            |
| 3      | u8        | Target platform, `w` (Windows)                   |
| 4      | u8        | Format version, `6`                              |
| 5      | u8        | Flags, `0` (uncompressed)                        |
| 6      | u32       | Total file size in bytes                         |

### Texture

| Offset | Type           | Value / meaning                                   |
| ------ | -------------- | ------------------------------------------------- |
| 10     | i32            | Surface format, `12` (`Alpha8`, 1 byte per pixel) |
| 14     | i32            | Atlas width                                       |
| 18     | i32            | Atlas height                                      |
| 22     | i32            | Mip level count, `1`                              |
| 26     | u32            | Pixel data size, `width * height`                 |
| 30     | bytes          | Pixel data, row-major, 0 = transparent            |

Atlas dimensions are not powers of two in shipped files (e.g. 1024 x 508), so any
size works.

### Glyph data

Immediately after the pixel data:

| Type                       | Meaning                                                    |
| -------------------------- | ---------------------------------------------------------- |
| varint N, N x Rect         | Glyph rectangles in the atlas                              |
| varint N, N x Rect         | Cropping: placement of each glyph in its line cell         |
| varint N, N x char         | The characters, sorted by code point                       |
| i32                        | Line spacing in pixels                                     |
| f32                        | Spacing: extra pixels after every glyph                    |
| i32                        | Cap height in pixels (height of `H`)                       |
| varint N, N x Vector3      | Kerning: left bearing, width, right bearing (f32 each)     |
| u8                         | `1` if a default character follows, else `0`               |
| char                       | Default character (`*` in shipped files)                   |

A `Rect` is four i32 values: x, y, width, height.

## Conventions in shipped files

- **Cropping.** `x` is always 0. `y` is the distance from the top of the line to the
  top of the glyph's ink. `width` is the truncated advance; `height` is the line
  spacing.
- **Baseline.** Blank glyphs (space, no-break space) have a `0`-height rectangle, and
  their cropping `y` is the baseline position. For inked glyphs, `cropping.y + rect.height`
  lands on the baseline (give or take antialiasing).
- **Blank glyphs** use a `3 x 0` rectangle and kerning `(0, 0, advance)`.
- **Small caps.** The `SC` in `P22UndergroundSC` and `SpectralSC` suggests small-caps
  fonts, where lowercase letters are stored as smaller capitals. This tool doesn't rely
  on the name: it detects small caps from glyph heights (`k` as short as `x`, both
  shorter than `X`).
- **Pen movement** follows XNA: add `kerning.left`, draw the glyph at
  `(pen + cropping.x, lineTop + cropping.y)`, then add `kerning.width + kerning.right + spacing`.

## Files in `bin/en` (as of the 1.0 release)

| File                                                                 | How this tool treats it                  |
| -------------------------------------------------------------------- | ---------------------------------------- |
| `LatoBold`, `LatoBold64`, `LatoBoldItalic`, `LatoItalic`, `LatoMedium`, `LatoSemibold`, `LatoSemiboldItalic` | Replaced |
| `P22UndergroundSCHeavy`, `P22UndergroundSCLight`, `P22UndergroundSCMedium` | Replaced (small caps kept if detected) |
| `SpectralSCExtraLight`, `SpectralSCLight`, `SpectralSCMedium`        | Replaced (small caps kept if detected)   |
| `CaesarDressing` (character names in dialogue)                       | Replaced                                 |
| `NotoSansMedium`                                                     | Replaced                                 |
| `MonospaceNumericP22UndergroundSCMedium`, `MonospaceTypewriterBold`  | Skipped unless `--include-mono`          |
| `ja`, `ko`, `zh-CN`, `zh-TW`, `Lang`                                 | Always skipped (CJK / language names)    |
