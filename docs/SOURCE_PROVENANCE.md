# v1.1.0 source and executable provenance

Reviewed artifact: `COTW_Toolkit/COTW_SoloHelper.exe` from the author's locally supplied Toolkit directory, examined 2026-10-28.

EXE SHA-256: `a2e840f6a08446b692b030d684de68c3882841bf85a1324730a8a61bae933034`.

The executable is not committed. No archive hash is asserted: an uploaded ZIP may be repackaged, and its hash must be calculated from that final upload.

All 31 embedded application modules match the published runtime source by Python bytecode, names, flags, exception tables and recursive constants, ignoring source paths/line metadata. See [SOURCE_COMPARISON.json](SOURCE_COMPARISON.json). This is semantic-code comparison, not a byte-for-byte rebuild guarantee or antivirus certification.

Data, offset profiles, icons and notices are copied from the examined distribution. Tests and build support are additional review materials. Current game resources, generated modifications, settings, save files, diagnostics and binaries are excluded. Previous v1.0.0 records remain in repository history.

The current source-build instructions are in [BUILD.md](../BUILD.md). An executable/hash compatibility gate is not proof of data-layout compatibility. Candidate or fallback behavior remains experimental.

The Helper is **not read-only**. It uses WriteProcessMemory for a native request target, temporary user-waypoint marker, and current pressure clearing. A legacy direct-position module is embedded for shared code but is not the current GUI route. Static game-owned resources are generated locally and installed only in navigator_solo; no game-resource fixtures are published. It does not inject DLLs, install drivers, execute remote game functions or bypass protections. Game saves can retain normal gameplay state effects.

Separated-source tests and successful rebuild: [VALIDATION_v1.1.0.md](VALIDATION_v1.1.0.md).
