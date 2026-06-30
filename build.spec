# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Children's Media Analysis Toolkit (CMAT).

Build with:
    python -m PyInstaller build.spec -y

Output: dist/CMAT/CMAT.exe
        dist/CMAT/config.json   (user-editable weights)
        dist/CMAT/_internal/ffmpeg.exe  (bundled)
"""

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        ('ffmpeg.exe', '.'),   # bundled ffmpeg — no PATH dependency for users
    ],
    datas=[
        ('config.json', '.'),
    ],
    hiddenimports=[
        # matplotlib backends
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
        # PIL plugins
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # pandas / numpy
        'pandas',
        'numpy',
        # scenedetect
        'scenedetect',
        'scenedetect.detectors',
        'scenedetect.detectors.content_detector',
        # cv2
        'cv2',
        # reportlab (PDF export)
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.platypus',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CMAT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # no black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CMAT',
)
