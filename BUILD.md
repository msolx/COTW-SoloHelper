# Build COTW Solo Helper for Windows x64

## Requirements

Use Windows 10/11 x64 and Python **3.12 x64**. Python 3.12.3 and the pinned Qt/PyInstaller versions were used for the local source-build check. A game installation is not needed merely to build the executable or run the mocked tests.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Some optional original-asset tests are explicitly skipped when their local fixtures are absent. Do not download or redistribute game archives or populations to satisfy those tests. All standard tests use synthetic data or mocks, not a running game or real memory writes.

Run the GUI from source:

```powershell
.\.venv\Scripts\python.exe solo_helper_launcher.py
```

Build the onedir application:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm COTW_SoloHelper.spec
```

Expected output:

```text
dist/COTW_SoloHelper/
    COTW_SoloHelper.exe
    _internal/
        python312.dll
        PySide6/
        data/
        offsets/
        licenses/
        icons/
        ...
```

Keep the complete directory, including `_internal`. The spec uses `solo_helper_launcher.py`, onedir/windowed mode, no UPX, optimization level 0, version metadata in `version_helper.txt`, and `icons/helper.ico`.

There are no runtime hooks, injected DLLs, custom kernel drivers or administrator-elevation manifest in this spec. This does **not** mean the helper is read-only: specific runtime features explicitly open write handles and use WriteProcessMemory, as documented in the README.

Add the project LICENSE, README and notices to a binary distribution, retain collected library licenses, and ZIP the generated onedir directory. Never package the parent workspace, private `.git` history, local settings/logs or original/generated game resources.

```powershell
Get-FileHash .\dist\COTW_SoloHelper\COTW_SoloHelper.exe -Algorithm SHA256
```

Rebuilt files may have different hashes due to build environment/metadata. These steps are rebuild instructions, not a promise of byte-identical binaries, absence of malware detections, or live-game compatibility. See [source provenance](docs/SOURCE_PROVENANCE.md) for the previously examined package's exact hashes and the application-module comparison.

## Real-game use is separate from building

Mod generation at runtime requires the user's own supported game, with exact EXE/build/resource hashes. Static settings require normal game exit, local generation/installation, and the helper's dedicated Mod launch. Waypoint and pressure features require explicit single-player UI confirmation and appropriate normal Windows access. Build/test commands do not start the game, install a Mod, arm a waypoint, or clear pressure.

The helper writes settings/status under its own local directory; frozen builds include a Local AppData fallback when their adjacent directory cannot be created. Game-installation permissions can still cause a controlled install refusal. Do not solve that by disabling protection.
