# Contributing

Thanks for helping! Bug reports, fixes and support for more game files are all welcome.

## Ground rules

- **Never commit fonts or game files.** Commercial fonts and Supergiant's `.xnb`
  files can't be redistributed. The pre-commit hook and `.gitignore` block them; the
  openly licensed fixtures in `tests/fixtures/` are the only exception.
- Keep the format reader byte-exact: `xnb.dumps(xnb.loads(data)) == data` must hold
  for every shipped game file.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync
uv run pre-commit install
```

## Before opening a pull request

```sh
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```

If you own the game, also run the real-file tests:

```sh
HADES2_FONTS_DIR="/path/to/Hades II/Content/Fonts/bin/en" uv run pytest
```

Add a line under **Unreleased** in `CHANGELOG.md` for any user-facing change.

## Releasing (maintainers)

1. Update `version` in `pyproject.toml`.
2. Run `uv lock` so the lockfile records the new version.
3. In `CHANGELOG.md`, rename **Unreleased** to the new version with today's date,
   add a fresh empty **Unreleased** section, and update the links at the bottom.
4. Commit, then tag and push:

   ```sh
   git commit -am "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

The **Release** workflow checks that the tag matches `pyproject.toml`, builds the
wheel, sdist, and Windows/Linux executables, smoke-tests the executables, and publishes
a GitHub release with checksums and the changelog entry as release notes.
