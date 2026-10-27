# Helper manual-review email draft

Use only if the actual Helper upload is quarantined. Replace `[HELPER MOD PAGE URL]` with that listing's URL; the separate radar page must not be represented as the Helper page. The author sends the support request; nothing in this repository sends email or edits Nexus.

```text
To: support@nexusmods.com
Subject: Manual review request - COTW SoloHelper V1.0.0

Hello Nexus Mods Support,

My COTW SoloHelper V1.0.0 upload was quarantined by the automated safety
checks. Could you please review it?

Mod page:
[HELPER MOD PAGE URL]

Helper-only source:
https://github.com/msolx/COTW-SoloHelper

Build instructions:
https://github.com/msolx/COTW-SoloHelper/blob/main/BUILD.md

This is an unofficial single-player modification tool for theHunter:
Call of the Wild. Unlike my separate read-only radar, the Helper uses
standard Windows WriteProcessMemory calls for explicitly confirmed
waypoint fast-travel redirection, temporary waypoint marker changes
and clearing existing hunting pressure. It also generates selected
static parameter mods locally from the user's own game installation.

It does not inject DLLs, install kernel drivers, hook game functions,
remotely execute game functions or bypass game/system protection.
It does not directly edit save files, although the game can save the
state effects of normal play after using the tool.

The Windows distribution bundles Python/Qt runtime libraries and is
built with Python 3.12, PySide6-Essentials 6.8.3 and PyInstaller 6.22.3
in onedir mode without UPX. docs/SOURCE_PROVENANCE.md documents the
examined local artifact hashes and the source comparison.

No antivirus clearance is claimed. Please let me know if a specific
detection, packaging issue or additional build information is needed.

Thank you for your help.

Best regards,
msolx (GitHub)
```
