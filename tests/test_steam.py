from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hades2_font_swap import steam


def _make_library(path: Path, with_game: bool) -> None:
    (path / "steamapps" / "common").mkdir(parents=True)
    if with_game:
        (path / "steamapps" / "common" / steam.GAME_FOLDER / "Content").mkdir(parents=True)


def _write_vdf(root: Path, libraries: list[Path]) -> None:
    entries = "\n".join(
        f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{str(lib).replace(chr(92), chr(92) * 2)}"\n\t}}'
        for i, lib in enumerate(libraries)
    )
    text = f'"libraryfolders"\n{{\n{entries}\n}}\n'
    (root / "steamapps" / "libraryfolders.vdf").write_text(text, encoding="utf-8")


def test_finds_game_in_secondary_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, second = tmp_path / "Steam", tmp_path / "SteamLibrary"
    _make_library(root, with_game=False)
    _make_library(second, with_game=True)
    _write_vdf(root, [root, second])
    monkeypatch.setattr(steam, "steam_roots", lambda: [root])

    assert steam.library_folders(root) == [root, second]
    assert steam.find_game_dir() == second / "steamapps" / "common" / steam.GAME_FOLDER


def test_game_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "Steam"
    _make_library(root, with_game=False)
    monkeypatch.setattr(steam, "steam_roots", lambda: [root])
    assert steam.find_game_dir() is None


def test_library_without_vdf(tmp_path: Path) -> None:
    _make_library(tmp_path, with_game=False)
    assert steam.library_folders(tmp_path) == [tmp_path]


def test_steam_roots_only_returns_real_installs() -> None:
    for root in steam.steam_roots():
        assert (root / "steamapps").is_dir()


@pytest.mark.skipif(sys.platform == "win32", reason="WSL path mapping is Linux-only")
def test_wsl_drive_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(steam, "_is_wsl", lambda: True)
    assert steam._from_windows_path(r"D:\SteamLibrary") == Path("/mnt/d/SteamLibrary")


@pytest.mark.skipif(sys.platform == "win32", reason="Linux path handling")
def test_linux_paths_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(steam, "_is_wsl", lambda: False)
    assert steam._from_windows_path("/home/me/Steam") == Path("/home/me/Steam")
