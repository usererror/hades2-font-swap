# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-10-10

### Added

- `apply`, `restore` and `info` commands, plus an interactive mode when run with no
  arguments (for example by double-clicking the Windows executable).
- Reader and writer for Hades II's version 6 font `.xnb` files, verified byte-identical
  against shipped game files.
- Automatic Steam library detection on Windows, Linux, Steam Deck (Flatpak) and WSL.
- Matching of the original cap height, baseline and line spacing.
- Fallback to original glyphs for characters the replacement font lacks.
- Small-caps detection.
- Automatic backup with a manifest, so game updates refresh the backup.
- Standalone Windows and Linux executables built by GitHub Actions.

[Unreleased]: https://github.com/usererror/hades2-font-swap/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/usererror/hades2-font-swap/releases/tag/v1.0.0
