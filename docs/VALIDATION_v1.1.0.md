# v1.1.0 historical source validation

Recorded on 2026-10-28 for source at tag `v1.1.0`, commit `9263691beb8ed730ee87104433f754bf7ac1c2a4`.

- Source suite: 102 tests executed, 98 passed, 4 skipped, zero failures/errors. Skips require original local game resources, which are deliberately not published.
- Configuration was initialized against a nonexistent test game path. The real path finder was then restored for temporary-directory tests. No running-game writes were performed.
- A separated-source PyInstaller build succeeded with Python 3.12.3 x64, PySide6-Essentials 6.8.3, PyInstaller 6.22.3 and hooks 2026.9. The output was not run for that build check.
- The originally inspected Toolkit EXE had SHA-256 `a2e840f6a08446b692b030d684de68c3882841bf85a1324730a8a61bae933034`, and its 31 application modules matched that source. This is not the standalone Release EXE.

The actual standalone GitHub Release ZIP was separately rechecked against the release-tag source. Its ZIP/EXE identities and 31-module static comparison are recorded in [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) and [SOURCE_COMPARISON.json](SOURCE_COMPARISON.json).

No GUI or real-game feature acceptance for the standalone Release ZIP is inferred from the source tests, build success or Toolkit comparison. No antivirus clearance is claimed. Private build/test logs are retained locally because they contain machine paths.
