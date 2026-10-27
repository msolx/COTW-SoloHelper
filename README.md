# COTW Solo Helper

A standalone Windows **single-player** helper for *theHunter: Call of the Wild*: temporary waypoint fast-travel, local movement/carrying-capacity parameter mods, extended spotting, FOXPRO parameters, and clearing existing hunting pressure.

**This tool is not read-only.** Its runtime features use standard Windows APIs, including `WriteProcessMemory`, to change narrowly scoped game state after explicit UI confirmation. Static mods are generated locally from the user's own game resources. It does not inject DLLs, install drivers, hook game functions, remotely execute game functions, or bypass protection.

[中文说明](docs/README.zh-CN.md) · [Build instructions](BUILD.md) · [Source provenance](docs/SOURCE_PROVENANCE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

## Compatibility

- Windows 10/11 x64, Steam, **single-player only**.
- Steam game build **25131233**, executable SHA256:
  `89dbab025114090c91a63ae7f0533ee84eee3c48f4b8543224b359c31b794c22`.
- Build/development: Python **3.12 x64**, PySide6-Essentials **6.8.3**, PyInstaller **6.22.3**.
- A game update may invalidate offsets, code checks and resource hashes. Do not force the compatibility checks to pass.

## Features and actual limits

| Feature | Implementation and limits |
|---|---|
| Waypoint fast-travel | Temporarily changes the user's map waypoint into a tent-style fast-travel icon. The user clicks it in game; the helper redirects one early native request and restores its temporary marker state. It creates no real tent entity. Arbitrary terrain/water/obstacle safety is **not guaranteed**. |
| Crouch speed | Static ordinary keyboard-crouch multiplier, 1–10×; default 1.5×. A compensating Shift modifier preserves the configured product. This is not runtime hot adjustment; noise can increase and original-noise behavior is not solved. |
| Base carry capacity | Default 512 kg, including an absolute Pack Mule-capacity adjustment so that skill does not reset it. Does not change item weights or remove backpack bonuses. |
| Spotting duration | Sets both Tag skill-level time parameters, default 120 s, configurable 120–999 s. Requires the relevant learned Tag skill; unloading/other normal marker rules can still clear a highlight. Not a universal persistent outline. |
| FOXPRO X360 | Optional 400 m remote-caller range and 1.0 **base** response probabilities. Other AI conditions/modifiers remain; this is not proof that every animal will approach. Does not merely change equipment UI text. |
| Existing pressure | One-shot clearing of the current reserve's existing pressure buffer with native refresh notification. It does **not** stop future pressure or restore deleted need zones. The game can persist the resulting state during normal saves. |

The GUI has four pages: waypoint travel, single-player parameters, pressure, and operation logs. The helper does not automatically prevent selection of the game's multiplayer menu; the single-player checkbox is a user confirmation, not a verified multiplayer detector.

The current native-travel configuration removes a fixed horizontal limit, allows up to 1000 m height difference, and includes relaxed mesh tolerances and a waypoint-height fallback. These are implementation limits/choices, **not a safety certification**. A fallback can accept a waypoint without independently confirmed final ground height. Check the operation log and actual landing; failed/unknown landing checks must not be described as success.

## Run from source

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe solo_helper_launcher.py
```

### Static parameter mods

1. Completely exit the game normally.
2. Open the helper and confirm single-player use. Configure the desired parameters.
3. Choose **Apply settings**. The worker checks that the game is closed, reads and validates original local resources, builds selected patches, and installs only into its owned `navigator_solo` game subdirectory.
4. Choose **Launch game with Mod**. Enter single-player only.
5. Check the actual result in game. Changing a UI number alone does not update a running game.

The original EXE/ARC files are not overwritten. The installer checks its manifest/owner/hashes and refuses unknown or externally changed files. To uninstall, exit the game and use the maintenance menu. Existing Steam launch options/other mods can still conflict; the helper does not silently remove them.

Generated resources in `solo_helper/work`, `solo_helper/output` or the game `navigator_solo` folder contain game-owned material. **Do not upload those resources to this repository or redistribute them.** Generate them from each user's own legitimate installation.

### Waypoint travel

1. Enter a supported single-player reserve. Place a user waypoint on dry, unobstructed land you can assess.
2. In the helper, optionally run the read-only waypoint check. Confirm single-player and this specific ground choice.
3. Click **Enable temporary tent** or press **Ctrl+Shift+T while the Helper window has focus**.
4. Wait for “Ready”, return to the game map, and click that temporary waypoint icon's Fast Travel option **once**. Do not reset the waypoint or choose a real tent while armed.
5. Let loading/observation/cleanup finish and inspect landing and movement. Marker ownership and error checks can stop an operation. Do not repeatedly retry a failed write.

Cancel waiting before the request is submitted when needed. Cancellation does not teleport back after the game has accepted a request. The helper refuses to close while an active operation still needs cleanup. If cleanup cannot safely restore a marker, keep the log and use normal game controls to remove/reset the waypoint.

### Pressure

Read the current pressure, then use **Clear existing pressure** only when explicitly desired. Reopen the game map to inspect the result. This operation changes current game memory and may be saved by the game; it is not a save-file editor and is not a future-pressure toggle.

Other Helper-window shortcuts: **Ctrl+B** only builds files; **Ctrl+L** launches the installed mod. These are not global in-game shortcuts.

## Source review and tests

Start at `solo_helper_launcher.py` → `solo_helper/main.py` / `window_layout.py`.

- `builder.py` / `archives.py` / `adf.py` / `rtpc.py`: bounded local resource parsing and patch generation.
- `installer.py`: owned-directory install/uninstall and normal game launch.
- `native_request.py` / `native_request_trial.py` / `virtual_tent_marker.py`: request and marker writes, ownership and lifecycle checks.
- `pressure.py`: only the current reserve's pressure-buffer clearing.
- `position_trial.py`: legacy direct-position experiment functions remain because the published EXE embeds this module for shared player lookup; the current GUI exposes only the temporary-tent route. Do not treat legacy experiments as the recommended interface.
- `memory/process_reader.py`: shared read-only reader used by validation. The helper's write handles are opened separately in the specific writer modules.

Run offline tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Tests use synthetic memory, temporary installation directories and mocked Windows/game calls. A small existing optional class checks original local game assets; those tests skip when the assets are absent. No copyrighted game fixtures are included. A skip is not a pass, and unit/build success does not prove a safe landing or a live-game feature result.

## Safety, privacy and licensing

This is an unofficial modification tool. Compatibility, account risk, crash risk and arbitrary-destination safety are not guaranteed. Use single-player only; normal game saves can preserve some state effects. If system/game protections deny access, stop. Do not disable antivirus, weaken protection or bypass permissions.

No private saves, Steam IDs, workstation paths, crash dumps, local settings or historical session logs are included. No application memory-upload/telemetry feature is implemented. Logs generated during use can contain coordinates/diagnostic details; do not publish them unredacted.

A PyInstaller executable may be unsigned or quarantined by a distribution platform. This repository does not assert antivirus clearance or automatically remove Nexus quarantine. Reviewers should use the explicit write-scope disclosures above, source/build documentation and artifact provenance.

Project source: [MIT License](LICENSE). External dependencies/research notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
