# -*- mode: python ; coding: utf-8 -*-
"""Lean, separate PyInstaller bundle for the participant Study Runner.

Build with:  python -m PyInstaller study_runner.spec -y --distpath dist/_staging
Output:      dist/_staging/CMAT Study Runner/

DO NOT build into a folder holding a study package or participant data. COLLECT
clears its output directory first, so building over a deployment deletes the
frozen clips and every collected response as an ordinary part of succeeding.
study_runner/README.md has the staging build and the copy that updates a
deployment without touching study/ or participant_data/.

No analyzer modules, OpenCV, NumPy, pandas, speech models, or coding tools are
imported by this entry point. Qt Multimedia supplies ordinary participant
playback; frame-accurate coding is not part of this application.

One module is shared with CMAT proper: `ui.tokens`, which imports no framework
and carries the pace scale's palette. PyInstaller pulls in `ui/__init__.py` and
`ui/tokens.py` and nothing else from that package — keep `ui/__init__.py` free
of imports, or this bundle stops being lean.
"""

a = Analysis(
    ["study_runner_qt.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[
        "analyzer", "cv2", "numpy", "pandas", "matplotlib", "scenedetect",
        "spacy", "faster_whisper", "torch", "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="CMAT Study Runner", console=False, debug=False, strip=False, upx=False,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, name="CMAT Study Runner",
)
