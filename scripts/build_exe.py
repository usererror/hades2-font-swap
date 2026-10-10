"""Build a single-file executable with PyInstaller.

Usage: uv run python scripts/build_exe.py [output-name]
The result lands in dist/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "hades2-font-swap"
    PyInstaller.__main__.run(
        [
            str(ROOT / "src" / "hades2_font_swap" / "__main__.py"),
            "--onefile",
            "--console",
            "--clean",
            "--noconfirm",
            "--name",
            name,
            # importlib.metadata needs this to report --version inside the bundle
            "--copy-metadata",
            "hades2-font-swap",
            # fontTools loads table modules dynamically, so PyInstaller can't see them
            "--collect-submodules",
            "fontTools.ttLib.tables",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build"),
            "--specpath",
            str(ROOT / "build"),
        ]
    )


if __name__ == "__main__":
    main()
