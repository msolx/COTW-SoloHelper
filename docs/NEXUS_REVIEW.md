# Manual review email draft

The author sends this message from the email associated with the Nexus account. Verify the username and upload the corresponding v1.1.0 artifact before sending. This draft does not send email or certify Nexus/antivirus approval.

```text
To: support@nexusmods.com
Subject: Manual review request - COTW SoloHelper v1.1.0 (Mod 1195)

Hello Nexus Mods Support,

My previous upload was quarantined by the automated safety checks. I have
prepared an updated v1.1.0 and published its corresponding separated source
and build instructions. Could you please manually review the updated file?

Nexus username: Zacks
Mod page: https://www.nexusmods.com/thehuntercallofthewild/mods/1195

Source code: https://github.com/msolx/COTW-SoloHelper
Build instructions: https://github.com/msolx/COTW-SoloHelper/blob/main/BUILD.md
Source/artifact verification:
https://github.com/msolx/COTW-SoloHelper/blob/main/docs/SOURCE_PROVENANCE.md

This is a single-player modification tool and is NOT read-only. It uses
standard Windows WriteProcessMemory calls for temporary waypoint-marker
changes, redirecting one native fast-travel request, and clearing existing
hunting pressure. Static mods are generated locally from the user's own
game resources and installed only under navigator_solo. Game state effects
may be persisted by normal game saves; the tool does not directly edit saves.
It does not inject DLLs, install drivers, hook game functions, execute
remote game functions or bypass game/system protection.

The Windows application uses Python 3.12 x64, PySide6-Essentials 6.8.3 and
PyInstaller 6.22.3 in onedir mode, with UPX disabled. The separated source
build was tested successfully. Original game assets, saves, private
settings, diagnostics and credentials are not included in the repository.
Compatibility with unverified game versions is explicitly experimental.

The locally reviewed COTW_SoloHelper.exe has SHA-256:
a2e840f6a08446b692b030d684de68c3882841bf85a1324730a8a61bae933034

All 31 embedded application modules matched the published runtime source
by bytecode/constants comparison. This is not a claim of byte-identical
rebuilds or antivirus clearance. If the submitted file has a specific
detection, please let me know what additional information is needed.

Thank you for your help.

Best regards,
Zacks
```
