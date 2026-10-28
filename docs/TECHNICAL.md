# Technical details — current application v1.1.0

For player instructions, see [README](../README.md). Hashes and binary/source correspondence are kept in [release provenance](SOURCE_PROVENANCE.md).

## Memory and file operations

Runtime actions are not read-only. `native_request.py` writes one native-request target, `virtual_tent_marker.py` temporarily changes the user waypoint marker, and `pressure.py` clears the active reserve's existing pressure with refresh notification. These use separate WriteProcessMemory handles after confirmation. `position_trial.py` is also embedded for shared lookup/legacy direct-position experiments; the current GUI exposes the temporary-tent route, not that legacy route.

`builder.py`, `archives.py`, `adf.py` and `rtpc.py` read/patch local game resources. `installer.py` manages owned files under navigator_solo and launches the game; it does not install into shared dropzone. Other mods can still conflict through resource/launch ordering. Generated game-owned resources must not be redistributed. No direct save-file editing is implemented, but game saves can preserve resulting state.

The native-travel path has no fixed horizontal limit, allows the configured 1000 m height difference, and includes mesh/waypoint-height fallbacks. This does not establish water/obstacle safety or final ground height everywhere. Tag requires the learned skill; clearing pressure does not prevent future pressure. Static movement patches compensate Shift's multiplier product, but original-noise behavior and runtime speed adjustment are not established.

Neither tool implements DLL injection, kernel drivers, remote game-function execution or protection bypass. A single-player checkbox is a user confirmation, not automatic multiplayer detection. If Windows/game protections deny access, stop.

## Compatibility and local paths

The existing field observations concern game build 25131233 (EXE `89dbab025114090c91a63ae7f0533ee84eee3c48f4b8543224b359c31b794c22`). Build 26051119 (`33c8306e52c5541a5b87e4af576f4149f3da0c23b36775372ec6c41adbab73ca`) is a candidate, not fully observed feature compatibility.

Packaged compatibility mode permits unknown EXE hashes to try existing layouts; source guards can be stricter. Fixed pointer/type/instruction checks and original-resource hashes remain. Recognizing an EXE or directory does not verify every writer or parameter resource on that game build.

Installation discovery supports running-game/Steam-library information, common paths and saved custom game directories. Save discovery currently looks under Documents/Avalanche Studios/COTW/Saves and selects a recently modified numeric account folder. This is a heuristic; it is not guaranteed for Epic/custom save layouts or multiple accounts. Store detection and memory-layout compatibility are separate concerns.

Source/build dependencies and commands are in [BUILD.md](../BUILD.md). Synthetic tests, successful compilation and binary comparison are not substitutes for clean-machine or real-game acceptance. Logs and configuration may contain private paths/coordinates and should remain local.
