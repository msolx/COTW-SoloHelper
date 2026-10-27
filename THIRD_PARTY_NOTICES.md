# Third-party notices

Project code is provided under the MIT License in `LICENSE`. The game, original resources, generated game-resource mods, saved populations and third-party executables are not covered by that license and are not committed here.

## Mod Builder / DECA and format research

TAB, AAF, SARC, ADF, RTPC and field research references:
<https://github.com/RyMaxim/cotw-mod-builder> at `3ac2b0c8ea61c822f47bcdd6ad54f3ab7a65adeb`.
Its MIT notice is retained in `licenses/ModBuilder-MIT.txt`; DECA lineage includes Krzysztof Kamieniecki. Parsers and narrowly scoped patching are implemented here without running the upstream mod-builder executable.

The Jenkins lookup3 algorithm used for resource-name hashes was published by Bob Jenkins for unrestricted use. No NumPy/Numba/mmh3 binary dependency is introduced by the pure-Python hash implementation.

The included shared attribute/trophy metadata references
<https://github.com/Pure-Winter-hue/apc-pw> at `8f297b5a9d36cfa826a18977dc4bd8c129bfc6ce`; its MIT text is in `licenses/apc-pw-MIT.txt`. Shared data/config are retained because the published packaging includes them; this repository does not provide the Animal Radar UI or upstream save-editing/injection code.

## Qt / PySide6 / shiboken6

Runtime dependency: PySide6-Essentials 6.8.3 with matching shiboken6. These dependencies are not vendored in this source tree. They are distributed under their applicable open-source/commercial terms, independently of the project's MIT license.

Full LGPLv3 and GPLv3 texts are retained in `licenses/LGPL-3.0.txt` and `licenses/GPL-3.0.txt`, obtained from official `qt/qtbase` tag `v6.8.3`. The Qt notice is also included.

- Qt source: <https://code.qt.io/cgit/qt/qtbase.git/> (v6.8.3).
- PySide/shiboken source: <https://code.qt.io/cgit/pyside/pyside-setup.git/> (v6.8.3).
- Qt for Python licensing details: <https://doc.qt.io/qtforpython-6.8/licenses.html>.

Binary distributors must retain applicable third-party notices and meet the source/replacement/library obligations of the components they actually ship. Separate onedir libraries must not be concealed or prevented from replacement. This is not a complete compliance certification for arbitrary distributions.

## Python / PyInstaller

Python's runtime has separate license terms: <https://docs.python.org/3/license.html>.
PyInstaller is an external build dependency with its bootloader exception: <https://pyinstaller.org/en/stable/license.html>.
Interpreter, Qt, build-tool and game binaries are excluded from the source repository. The spec includes library-license files for subsequent binary packaging.
