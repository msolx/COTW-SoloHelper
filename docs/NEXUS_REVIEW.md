# Nexus review information — v1.1.0

This page describes the public release and its review material. Personal email drafts and support correspondence are kept locally, not in this repository. Providing source is not a claim of Nexus approval or antivirus clearance.

- Mod page: https://www.nexusmods.com/thehuntercallofthewild/mods/1195
- Published file: https://github.com/msolx/COTW-SoloHelper/releases/tag/v1.1.0
- Runtime source (fixed release tag): https://github.com/msolx/COTW-SoloHelper/tree/v1.1.0
- Build instructions (fixed tag): https://github.com/msolx/COTW-SoloHelper/blob/v1.1.0/BUILD.md
- Corrected artifact provenance (fixed documentation tag): https://github.com/msolx/COTW-SoloHelper/blob/docs-2026-10-28/docs/SOURCE_PROVENANCE.md
- Per-module comparison (fixed documentation tag): https://github.com/msolx/COTW-SoloHelper/blob/docs-2026-10-28/docs/SOURCE_COMPARISON.json
- Validation scope (fixed documentation tag): https://github.com/msolx/COTW-SoloHelper/blob/docs-2026-10-28/docs/VALIDATION_v1.1.0.md
- Technical operations/limits (fixed documentation tag): https://github.com/msolx/COTW-SoloHelper/blob/docs-2026-10-28/docs/TECHNICAL.md

## Artifact identity

File: `COTW_SoloHelper_v1.1.0.zip`

ZIP SHA-256: `a7d8d92ffdd2f592ddab815bfbecb7e49ee6d91cbe245ba50daf5b97048d466b`

EXE SHA-256: `0f3c1a9326f1a82d15e1c8545d00020cf1c27ff23b21592d8710ab6ed3b4f8d8`

The local ZIP matches the GitHub asset digest/size, and all 31 embedded application modules match the release-tag source. This review did not execute the EXE or retest game features; the linked validation record distinguishes earlier source tests from released-binary checks.

## Actual operation

This application is not read-only. Explicitly confirmed waypoint-request/marker and current-pressure actions use WriteProcessMemory. Static mods are generated locally from game-owned resources and installed in navigator_solo. It does not directly edit save files, but normal game saves can persist state effects. A legacy direct-position module remains embedded for shared code; the GUI route is temporary-tent travel.

Single-player use only. Compatibility with unverified builds/channels is experimental. No DLL injection, drivers, game-function hooks, remote game-function execution or protection bypass is implemented. The Windows distribution uses Python 3.12 x64, PySide6-Essentials 6.8.3 and PyInstaller 6.22.3 in onedir mode without UPX.

No personal settings, saves, diagnostics or generated game resources are required in the public source. Rebuilt bytes may differ. Current source attribution changes do not rewrite metadata or license files inside the existing release ZIP.
