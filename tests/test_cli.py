from __future__ import annotations

import json
from pathlib import Path

import pytest

from fontfactory import REPLACEMENT_FONT, make_game_font
from hades2_font_swap import backup, cli, xnb

FONT = str(REPLACEMENT_FONT)


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.glob("*.xnb"))}


def _apply(game_dir: Path, *extra: str) -> int:
    return cli.main(["apply", "--font", FONT, "--game-dir", str(game_dir), *extra])


def test_apply_replaces_eligible_fonts(game_dir: Path, fonts_dir: Path) -> None:
    before = _snapshot(fonts_dir)
    assert _apply(game_dir) == 0
    after = _snapshot(fonts_dir)

    for name in ("LatoBold.xnb", "LatoBold64.xnb", "P22UndergroundSCMedium.xnb"):
        assert after[name] != before[name]
        xnb.loads(after[name])  # still a valid font file
    assert after["ja.xnb"] == before["ja.xnb"]
    assert after["MonospaceTypewriterBold.xnb"] == before["MonospaceTypewriterBold.xnb"]
    assert _snapshot(backup.backup_dir_for(fonts_dir)) == before


def test_include_mono(game_dir: Path, fonts_dir: Path) -> None:
    before = _snapshot(fonts_dir)
    assert _apply(game_dir, "--include-mono") == 0
    name = "MonospaceTypewriterBold.xnb"
    assert _snapshot(fonts_dir)[name] != before[name]


def test_apply_is_repeatable(game_dir: Path, fonts_dir: Path) -> None:
    assert _apply(game_dir) == 0
    first = _snapshot(fonts_dir)
    assert _apply(game_dir) == 0
    assert _snapshot(fonts_dir) == first


def test_game_update_refreshes_backup(game_dir: Path, fonts_dir: Path) -> None:
    assert _apply(game_dir) == 0
    patched = xnb.dumps(make_game_font(size=26.0))  # a "new original" shipped by a patch
    (fonts_dir / "LatoBold.xnb").write_bytes(patched)

    assert _apply(game_dir) == 0
    backup_dir = backup.backup_dir_for(fonts_dir)
    assert (backup_dir / "LatoBold.xnb").read_bytes() == patched
    assert (fonts_dir / "LatoBold.xnb").read_bytes() != patched


def test_restore(game_dir: Path, fonts_dir: Path) -> None:
    before = _snapshot(fonts_dir)
    assert _apply(game_dir) == 0
    assert cli.main(["restore", "--game-dir", str(game_dir)]) == 0
    assert _snapshot(fonts_dir) == before


def test_restore_without_backup(game_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["restore", "--game-dir", str(game_dir)]) == 1
    assert "no backup" in capsys.readouterr().err


def test_dry_run_writes_nothing(game_dir: Path, fonts_dir: Path) -> None:
    before = _snapshot(fonts_dir)
    assert _apply(game_dir, "--dry-run") == 0
    assert _snapshot(fonts_dir) == before
    assert not backup.backup_dir_for(fonts_dir).exists()


def test_fonts_dir_override(fonts_dir: Path) -> None:
    assert cli.main(["apply", "--font", FONT, "--fonts-dir", str(fonts_dir)]) == 0


def test_manifest_records_written_files(game_dir: Path, fonts_dir: Path) -> None:
    assert _apply(game_dir) == 0
    manifest_path = backup.backup_dir_for(fonts_dir) / backup.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {"LatoBold.xnb", "LatoBold64.xnb", "P22UndergroundSCMedium.xnb"}


def test_legacy_backup_without_manifest_is_trusted(game_dir: Path, fonts_dir: Path) -> None:
    original = _snapshot(fonts_dir)
    assert _apply(game_dir) == 0
    backup_dir = backup.backup_dir_for(fonts_dir)
    (backup_dir / backup.MANIFEST_NAME).unlink()

    assert _apply(game_dir) == 0
    assert _snapshot(backup_dir) == original


def test_corrupt_font_is_reported_and_left_original(
    game_dir: Path, fonts_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (fonts_dir / "Broken.xnb").write_bytes(b"not a font")
    assert _apply(game_dir) == 1
    assert "Broken.xnb" in capsys.readouterr().err
    assert (fonts_dir / "Broken.xnb").read_bytes() == b"not a font"


def test_missing_font_file(game_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["apply", "--font", "nope.ttf", "--game-dir", str(game_dir)])
    assert code == 1
    assert "font file not found" in capsys.readouterr().err


def test_unreadable_font_file(
    game_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bogus = tmp_path / "bogus.ttf"
    bogus.write_bytes(b"\x00" * 64)
    assert cli.main(["apply", "--font", str(bogus), "--game-dir", str(game_dir)]) == 1
    assert "cannot read font" in capsys.readouterr().err


def test_game_not_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "find_game_dir", lambda: None)
    assert cli.main(["apply", "--font", FONT]) == 1
    assert "couldn't find Hades II" in capsys.readouterr().err


def test_bad_language_folder(game_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["restore", "--game-dir", str(game_dir), "--lang", "xx"]) == 1
    assert "font folder not found" in capsys.readouterr().err


def test_info(fonts_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["info", str(fonts_dir / "LatoBold.xnb")]) == 0
    out = capsys.readouterr().out
    assert "line spacing  40" in out
    assert "glyphs" in out


def test_info_bad_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.xnb"
    bad.write_bytes(b"XNBw")
    assert cli.main(["info", str(bad)]) == 1
    assert "error:" in capsys.readouterr().err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "hades2-font-swap" in capsys.readouterr().out


def test_wizard_apply(game_dir: Path, fonts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["a", f'"{FONT}"', ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(cli, "find_game_dir", lambda: game_dir)
    before = _snapshot(fonts_dir)
    assert cli.wizard() == 0
    assert _snapshot(fonts_dir)["LatoBold.xnb"] != before["LatoBold.xnb"]


def test_wizard_restore_with_manual_path(
    game_dir: Path, fonts_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _snapshot(fonts_dir)
    assert _apply(game_dir) == 0
    answers = iter([str(game_dir), "r", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(cli, "find_game_dir", lambda: None)
    assert cli.wizard() == 0
    assert _snapshot(fonts_dir) == before
