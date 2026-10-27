# Helper source provenance

This is a separately initialized **COTW Solo Helper** repository prepared for public code/build review. It contains the published Helper's application source and the shared modules that its runtime imports. It does not contain the parent workspace's Git history, the Animal Radar UI, original/generated game resources, private saves, Steam identifiers, local settings, crash dumps or session logs.

## Examined local v1.0.0 distribution

| Artifact | SHA256 |
|---|---|
| `COTW_SoloHelper_v1.0.0.zip` | `9006db4c73fa453332abc43ac93e1de7ee333b1f69fb71e90f531670c42d9e6a` |
| Its `COTW_SoloHelper.exe` | `0e3017871347e0ca3714a2426ad050f5e23becf36e47c30e6c41f06d37629729` |

The local release manifest records assembly on 2026-10-27 at 16:53:55 +0800. A Nexus-hosted Helper file was not independently downloaded/hashed during this source preparation. These hashes identify the examined local file, not an unverified future upload or a newly rebuilt EXE.

The ZIP's EXE was compared byte-for-byte with the local dist EXE. Its PyInstaller CArchive/PYZ was then inspected without executing the application. **31 application entry/modules matched their copied source**, comparing instructions, names, argument flags, exception tables and recursively nested constants while ignoring filenames and line-number metadata. The detailed relative-path result is [SOURCE_COMPARISON.json](SOURCE_COMPARISON.json).

This comparison does not certify a native bootloader/DLL, perform antivirus clearance or prove live-game behavior. It preserves source traceability rather than replacing the application with a differently behaving sanitized implementation.

## Scope and intentional memory writes

Unlike the separate Animal Radar, this application **writes game memory** for selected single-player features. Important review locations:

- `solo_helper/native_request.py`: one early native destination XYZ write after request/instance checks.
- `solo_helper/virtual_tent_marker.py`: temporary user-waypoint type/session-reference changes and owned-state restoration.
- `solo_helper/pressure.py`: current-reserve pressure-buffer clearing and the native dirty/refresh flag.
- `solo_helper/position_trial.py`: legacy position/motion experiment code also embedded in the examined EXE for shared lookup functionality; the current GUI exposes the temporary-tent route only.
- `solo_helper/installer.py`: local owned `navigator_solo` directory writes; it refuses unexpected ownership/content/hash changes and does not overwrite original EXE/ARC files.

These operations use normal user-mode Windows APIs, not a driver, DLL injection, a function hook or remote game-function execution. Read-only inspection, static Mod installation and runtime state writes are different scopes and should not be conflated in a support request.

The current source includes the later relaxed terrain tolerances and waypoint-height fallback. Safe arbitrary-destination terrain/water/obstacle handling is not fully implemented or certified; this repository does not silently replace those choices with the earlier conservative distance limits.

## Public-source verification

The separated tree ran **97 tests: 93 passed and 4 explicitly skipped**. The skipped tests require locally extracted original game assets that are deliberately not distributed. Standard tests use mocked APIs/synthetic data/temporary folders and do not connect to or write a real game. Optional asset tests are not represented as passed.

Additional material is limited to public README/build/license documentation, tests, a read-only caller-range/probability probe, and review records. Build caches, binaries, source-preparation scripts containing private scan patterns and historical diagnostics remain outside this repository.

The separated source tree also built successfully using PyInstaller 6.22.3 with the supplied spec on Windows 10 x64, Python 3.12.3 and Qt 6.8.3. Build logs/caches and outputs are excluded from Git.

Build instructions are in [BUILD.md](../BUILD.md). This is compilation/packaging verification, not a real-game run, malware-free guarantee or automatic Nexus-quarantine approval.
