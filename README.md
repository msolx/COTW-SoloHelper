# COTW SoloHelper

**v1.1.0 · Windows 10/11 x64 · by msolx**

A single-player helper for *theHunter: Call of the Wild*.

[Download v1.1.0](https://github.com/msolx/COTW-SoloHelper/releases/tag/v1.1.0) · [中文说明](docs/README.zh-CN.md)

## Features

| Feature | What to expect |
| --- | --- |
| Waypoint fast-travel | Temporarily turns your waypoint into a tent-style fast-travel icon. You click it in the game map. Choose dry, unobstructed land; arbitrary landing safety is not guaranteed. |
| Crouch speed | Default 1.5×, adjustable from 1–10×. Requires restarting the game to apply. Noise can increase; runtime adjustment and prone-speed controls are not implemented. |
| Carry capacity | Default 512 kg base capacity; item weights and backpack bonuses remain. |
| Spotting duration | Default 120 seconds, adjustable to 999; requires the learned Tag skill. Normal unloading/marker rules still apply. |
| FOXPRO X360 | Optional 400 m range and 100% base attraction probability. Other animal AI conditions still affect responses. |
| Existing pressure | Clears the current reserve's existing pressure. Does not prevent future pressure or restore lost need zones. |

## Install

1. Download **COTW_SoloHelper_v1.1.0.zip** from the Release's **Assets**, not Source code.
2. Extract the whole ZIP to a writable folder. Keep `_internal` and companion files; Python is bundled.
3. Run `COTW_SoloHelper.exe`. If the game is not found, choose **Maintenance → Locate Game Directory** and select the folder containing `theHunterCotW_F.exe`.

## Use

**Static settings:** Exit the game normally, confirm single-player use, set the desired values and choose **Apply Settings**, then **Launch Game with Mods**. Changing a number alone does not update a running game. Mods install under `navigator_solo`; to remove them, exit the game and use **Maintenance → Uninstall Mod**. Other launch options/mods can still conflict.

**Waypoint travel:** In single-player, place a waypoint on dry, unobstructed land. Confirm single-player and the chosen ground in Helper, then arm the temporary tent. Wait for “Ready”, return to the map and click that temporary icon's Fast Travel **once**. Do not reset the waypoint or click a real tent while armed. Let loading and cleanup finish, then check landing and movement. Cancel waiting before submission if needed; cancellation does not undo an accepted teleport. Do not force-close Helper while cleanup is active.

**Pressure:** Read/clear existing pressure on the Pressure page, then reopen the game map. Later kills can create pressure again.

Helper-window shortcuts: **Ctrl+Shift+T** arms waypoint travel, **Ctrl+B** builds files, **Ctrl+L** launches with mods. These require Helper focus; they are not global game hotkeys.

## Important

**Single-player only. SoloHelper modifies game memory** for explicitly confirmed waypoint/pressure actions and creates local parameter mods. It does not directly edit save files, but normal game saving can preserve state changes. The single-player checkbox is not automatic multiplayer detection.

Game-version compatibility is not guaranteed; unverified stores/builds are experimental. If access or structure checks fail, stop. Do not disable security tools or bypass game protection. This unofficial tool does not guarantee safe landings, no crashes/account risk or no antivirus warnings.

Do not upload generated game resources, saves, settings or private logs with bug reports.

## More information

[Build from source](BUILD.md) · [Technical details](docs/TECHNICAL.md) · [Release provenance](docs/SOURCE_PROVENANCE.md) · [Nexus review information](docs/NEXUS_REVIEW.md)

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Nexus page](https://www.nexusmods.com/thehuntercallofthewild/mods/1195)
