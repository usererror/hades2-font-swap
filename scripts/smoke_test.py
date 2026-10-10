"""Run a built executable against a fake Hades II install.

Usage: python scripts/smoke_test.py path/to/hades2-font-swap[.exe]
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from fontfactory import REPLACEMENT_FONT, make_game_dir


def run(exe: str, *args: str) -> str:
    result = subprocess.run([exe, *args], capture_output=True, text=True, check=False)
    print(result.stdout, result.stderr, sep="")
    if result.returncode != 0:
        raise SystemExit(f"{args[0] if args else exe} exited with {result.returncode}")
    return result.stdout


def main() -> None:
    exe = sys.argv[1]
    print(run(exe, "--version"))
    with tempfile.TemporaryDirectory() as tmp:
        game = make_game_dir(Path(tmp))
        fonts = game / "Content" / "Fonts" / "bin" / "en"
        before = (fonts / "LatoBold.xnb").read_bytes()
        run(exe, "apply", "--font", str(REPLACEMENT_FONT), "--game-dir", str(game))
        assert (fonts / "LatoBold.xnb").read_bytes() != before, "font was not replaced"
        run(exe, "info", str(fonts / "LatoBold.xnb"))
        run(exe, "restore", "--game-dir", str(game))
        assert (fonts / "LatoBold.xnb").read_bytes() == before, "restore failed"
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
