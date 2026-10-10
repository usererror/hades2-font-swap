"""Command-line interface.

Run with no arguments (for example by double-clicking the .exe) to get an interactive
wizard; otherwise use the ``apply``, ``restore`` and ``info`` subcommands.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from hades2_font_swap import __version__, backup, xnb
from hades2_font_swap.rebuild import RebuildError, ReplacementFont, rebuild_font
from hades2_font_swap.steam import find_game_dir

NON_LATIN_FONTS = frozenset({"ja", "ko", "zh-CN", "zh-TW", "Lang"})
"""CJK fonts and the font that draws each language's own name; never replaced."""

MONOSPACE_PREFIX = "Monospace"
"""Fixed-width fonts for timers and counters; skipped unless ``--include-mono``."""

FONTS_SUBDIR = Path("Content", "Fonts", "bin")


class CliError(Exception):
    """A user-facing error; printed without a traceback."""


def _fonts_dir(args: argparse.Namespace) -> Path:
    if args.fonts_dir:
        fonts = Path(args.fonts_dir)
    else:
        game = Path(args.game_dir) if args.game_dir else find_game_dir()
        if game is None:
            raise CliError("couldn't find Hades II in your Steam libraries; pass --game-dir")
        fonts = game / FONTS_SUBDIR / args.lang
    if not fonts.is_dir():
        raise CliError(f"font folder not found: {fonts}")
    return fonts


def _should_skip(name: str, include_mono: bool) -> str | None:
    if name in NON_LATIN_FONTS:
        return "non-Latin font"
    if name.startswith(MONOSPACE_PREFIX) and not include_mono:
        return "monospace font (use --include-mono to replace)"
    return None


def cmd_apply(args: argparse.Namespace) -> int:
    """Rebuild every eligible font in the language folder with the chosen font."""
    font_path = Path(args.font)
    if not font_path.is_file():
        raise CliError(f"font file not found: {font_path}")
    fonts_dir = _fonts_dir(args)
    try:
        replacement = ReplacementFont(font_path)
    except RebuildError as exc:
        raise CliError(str(exc)) from exc

    if args.dry_run:
        backup_dir = backup.backup_dir_for(fonts_dir)
        source_dir = backup_dir if backup_dir.is_dir() else fonts_dir
        print(f"Dry run: reading originals from {source_dir}, writing nothing.")
    else:
        source_dir, refreshed = backup.sync_backup(fonts_dir)
        if refreshed:
            print(f"Backed up {len(refreshed)} original font(s) to {source_dir}")

    written: dict[str, Path] = {}
    failures = 0
    for original_path in sorted(source_dir.glob("*.xnb")):
        name = original_path.name
        reason = _should_skip(original_path.stem, args.include_mono)
        if reason:
            print(f"  skip     {name}: {reason}")
            continue
        try:
            result = rebuild_font(xnb.load(original_path), replacement)
        except (xnb.XnbFormatError, RebuildError) as exc:
            failures += 1
            print(f"  FAILED   {name}: {exc}", file=sys.stderr)
            if not args.dry_run:
                shutil.copy2(original_path, fonts_dir / name)  # never leave a half-swap
            continue
        detail = f"{result.replaced}/{result.total} glyphs"
        if result.small_caps:
            detail += ", small caps"
        if not args.dry_run:
            target = fonts_dir / name
            xnb.dump(result.font, target)
            written[name] = target
        print(f"  rebuilt  {name} ({detail})")

    if not args.dry_run:
        backup.record_written(source_dir, written)
        print(f"\nDone: {len(written)} font(s) replaced in {fonts_dir}")
    return 1 if failures else 0


def cmd_restore(args: argparse.Namespace) -> int:
    """Put the game's original fonts back."""
    fonts_dir = _fonts_dir(args)
    try:
        restored = backup.restore(fonts_dir)
    except FileNotFoundError as exc:
        raise CliError(str(exc)) from exc
    print(f"Restored {len(restored)} original font(s) in {fonts_dir}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Print a summary of one or more font files."""
    for raw in args.files:
        path = Path(raw)
        try:
            font = xnb.load(path)
        except (OSError, xnb.XnbFormatError) as exc:
            raise CliError(str(exc)) from exc
        chars = "".join(font.chars)
        print(f"{path.name}")
        print(f"  atlas         {font.width} x {font.height}")
        print(f"  glyphs        {len(font.chars)}")
        print(f"  line spacing  {font.line_spacing}")
        print(f"  cap height    {font.cap_height}")
        print(f"  spacing       {font.spacing}")
        print(f"  default char  {font.default_char!r}")
        print(f"  characters    {chars[:80]}{'...' if len(chars) > 80 else ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="hades2-font-swap",
        description="Replace Hades II's in-game fonts with any TTF/OTF font.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    location = argparse.ArgumentParser(add_help=False)
    location.add_argument("--game-dir", help="Hades II install folder (default: auto-detect)")
    location.add_argument("--lang", default="en", help="language folder to modify (default: en)")
    location.add_argument("--fonts-dir", help="use this font folder directly (overrides the above)")

    apply = sub.add_parser("apply", parents=[location], help="replace the game's fonts")
    apply.add_argument("--font", required=True, help="path to the .ttf or .otf font to use")
    apply.add_argument(
        "--include-mono", action="store_true", help="also replace monospace timer/number fonts"
    )
    apply.add_argument("--dry-run", action="store_true", help="rebuild in memory, write nothing")
    apply.set_defaults(func=cmd_apply)

    restore = sub.add_parser("restore", parents=[location], help="put the original fonts back")
    restore.set_defaults(func=cmd_restore)

    info = sub.add_parser("info", help="describe font .xnb files")
    info.add_argument("files", nargs="+", help=".xnb files to describe")
    info.set_defaults(func=cmd_info)
    return parser


def _ask(prompt: str) -> str:
    # Dragging a file onto a console window pastes its path, often wrapped in quotes.
    return input(prompt).strip().strip('"').strip("'")


def wizard() -> int:
    """Interactive mode for people who double-click the executable."""
    print(f"Hades II Font Swap {__version__}\n")
    game = find_game_dir()
    if game:
        print(f"Found Hades II at: {game}\n")
    else:
        game = Path(_ask("Couldn't find Hades II automatically. Paste its install folder: "))
    choice = _ask("Type A to apply a font or R to restore the originals, then press Enter: ")
    if choice.lower().startswith("r"):
        argv = ["restore", "--game-dir", str(game)]
    else:
        font = _ask("Drag your .ttf or .otf file onto this window, then press Enter: ")
        argv = ["apply", "--font", font, "--game-dir", str(game)]
    print()
    code = main(argv)
    input("\nPress Enter to close...")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list and sys.stdin.isatty():
        try:
            return wizard()
        except (EOFError, KeyboardInterrupt):
            return 130
    args = build_parser().parse_args(args_list)
    try:
        code: int = args.func(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except PermissionError as exc:
        print(
            f"error: permission denied writing {exc.filename}. "
            "Try running from an Administrator terminal.",
            file=sys.stderr,
        )
        return 1
    return code
