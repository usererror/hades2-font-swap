"""Keep pristine copies of the game's font files.

The backup lives next to the language folder (``bin/en`` -> ``bin/en_original_backup``).
A manifest records the hash of every file this tool writes. When the tool runs again,
any font whose hash is *not* in the manifest came from the game itself (a fresh install
or a patch), so it replaces the backup copy. That way rebuilding after a game update
always starts from the current originals, never from stale ones.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

BACKUP_SUFFIX = "_original_backup"
MANIFEST_NAME = ".hades2-font-swap.json"


def backup_dir_for(fonts_dir: Path) -> Path:
    """Where originals for ``fonts_dir`` are kept."""
    return fonts_dir.with_name(fonts_dir.name + BACKUP_SUFFIX)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest(backup: Path) -> dict[str, str] | None:
    path = backup / MANIFEST_NAME
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def _write_manifest(backup: Path, manifest: dict[str, str]) -> None:
    text = json.dumps(dict(sorted(manifest.items())), indent=2) + "\n"
    (backup / MANIFEST_NAME).write_text(text, encoding="utf-8")


def sync_backup(fonts_dir: Path) -> tuple[Path, list[str]]:
    """Make sure the backup holds the game's current original fonts.

    Returns the backup folder and the names of files that were (re)backed up.
    """
    backup = backup_dir_for(fonts_dir)
    if not backup.is_dir():
        shutil.copytree(fonts_dir, backup)
        _write_manifest(backup, {})
        return backup, sorted(p.name for p in fonts_dir.glob("*.xnb"))

    manifest = _read_manifest(backup)
    if manifest is None:
        # A backup without a manifest predates this tool's tracking. Trust it as-is
        # and start tracking from now on.
        _write_manifest(backup, {})
        return backup, []

    refreshed = []
    for current in sorted(fonts_dir.glob("*.xnb")):
        if manifest.get(current.name) != _sha256(current):
            shutil.copy2(current, backup / current.name)
            refreshed.append(current.name)
    return backup, refreshed


def record_written(backup: Path, written: dict[str, Path]) -> None:
    """Remember the hashes of files the tool just wrote (name -> path)."""
    manifest = _read_manifest(backup) or {}
    manifest.update({name: _sha256(path) for name, path in written.items()})
    _write_manifest(backup, manifest)


def restore(fonts_dir: Path) -> list[str]:
    """Copy every backed-up original over ``fonts_dir``. Returns the restored names."""
    backup = backup_dir_for(fonts_dir)
    if not backup.is_dir():
        raise FileNotFoundError(f"no backup found at {backup}")
    restored = []
    for original in sorted(backup.glob("*.xnb")):
        shutil.copy2(original, fonts_dir / original.name)
        restored.append(original.name)
    return restored
