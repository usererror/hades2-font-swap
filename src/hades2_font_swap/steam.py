"""Locate the Hades II install folder across Steam libraries.

Works on Windows (registry), Linux/Steam Deck (native and Flatpak Steam) and WSL
(reads the Windows Steam install through ``/mnt/<drive>``).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

GAME_FOLDER = "Hades II"
_LIBRARY_PATH = re.compile(r'"path"\s+"([^"]+)"')


def _registry_steam_root() -> Path | None:
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415 - Windows-only module

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return None
    return Path(str(value))


def _is_wsl() -> bool:
    return sys.platform == "linux" and "microsoft" in os.uname().release.lower()


def _from_windows_path(raw: str) -> Path:
    """Convert a Windows path from libraryfolders.vdf to one usable on this OS."""
    if sys.platform == "win32":
        return Path(raw)
    win = PureWindowsPath(raw)
    if _is_wsl() and win.drive:
        drive = win.drive.rstrip(":").lower()
        return Path(PurePosixPath("/mnt", drive, *win.parts[1:]))
    return Path(raw)


def steam_roots() -> list[Path]:
    """Candidate Steam installation folders for this machine."""
    candidates: list[Path] = []
    registry = _registry_steam_root()
    if registry:
        candidates.append(registry)
    if sys.platform == "win32":
        candidates.append(Path(r"C:\Program Files (x86)\Steam"))
    else:
        home = Path.home()
        candidates += [
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        ]
        if _is_wsl():
            candidates.append(Path("/mnt/c/Program Files (x86)/Steam"))
    return [p for p in dict.fromkeys(candidates) if (p / "steamapps").is_dir()]


def library_folders(steam_root: Path) -> list[Path]:
    """All Steam library folders registered under ``steam_root``."""
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        for raw in _LIBRARY_PATH.findall(vdf.read_text(encoding="utf-8", errors="replace")):
            libraries.append(_from_windows_path(raw.replace("\\\\", "\\")))
    return list(dict.fromkeys(libraries))


def find_game_dir() -> Path | None:
    """Return the Hades II install folder, or ``None`` if it cannot be found."""
    for root in steam_roots():
        for library in library_folders(root):
            game = library / "steamapps" / "common" / GAME_FOLDER
            if (game / "Content").is_dir():
                return game
    return None
