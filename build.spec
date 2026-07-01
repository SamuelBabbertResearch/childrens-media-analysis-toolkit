# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Children's Media Analysis Toolkit (CMAT).

Build with:
    python -m PyInstaller build.spec -y

Output:
    dist/CMAT/CMAT.exe          — launch the app
    dist/CMAT/config.json       — user-editable weights (next to exe)
    dist/CMAT/_internal/        — bundled Python + libraries

Requirements in dist/CMAT/:
    - ffmpeg.exe must be in the project root before building (already present)
    - Whisper model files are downloaded at first run to the user HuggingFace cache
      (~/.cache/huggingface/hub/); they are NOT bundled (would add ~1 GB)
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
import os, glob

# ── Collect complex packages that PyInstaller can't auto-detect ───────────────

# spaCy + English model (vocab complexity analysis)
spacy_datas,    spacy_bins,    spacy_hidden    = collect_all('spacy')
en_datas,       en_bins,       en_hidden       = collect_all('en_core_web_sm')

# ctranslate2 (Whisper inference engine — has native DLLs)
ct2_datas,      ct2_bins,      ct2_hidden      = collect_all('ctranslate2')

# faster-whisper (includes silero VAD onnx model)
fw_datas,       fw_bins,       fw_hidden       = collect_all('faster_whisper')

# thinc / blis / preshed / cymem (spaCy low-level deps)
thinc_datas,    thinc_bins,    thinc_hidden    = collect_all('thinc')
blis_datas,     blis_bins,     blis_hidden     = collect_all('blis')

# wordfreq English frequency data
import wordfreq as _wf
_wf_data_dir = os.path.join(os.path.dirname(_wf.__file__), 'data')
wordfreq_datas = [
    (os.path.join(_wf_data_dir, 'large_en.msgpack.gz'), 'wordfreq/data'),
]

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        ('ffmpeg.exe', '.'),    # bundled ffmpeg — no PATH dependency for users
        *spacy_bins,
        *en_bins,
        *ct2_bins,
        *fw_bins,
        *thinc_bins,
        *blis_bins,
    ],
    datas=[
        ('config.json', '.'),   # lands next to CMAT.exe so users can edit weights
        *spacy_datas,
        *en_datas,
        *ct2_datas,
        *fw_datas,
        *thinc_datas,
        *blis_datas,
        *wordfreq_datas,
    ],
    hiddenimports=[
        # matplotlib
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
        # PIL
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # pandas / numpy
        'pandas',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'numpy',
        # OpenCV
        'cv2',
        # PySceneDetect
        'scenedetect',
        'scenedetect.detectors',
        'scenedetect.detectors.content_detector',
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
        # wordfreq
        'wordfreq',
        'wordfreq.tokens',
        'msgpack',
        # textstat (readability metrics)
        'textstat',
        'textstat.textstat',
        # lexical-diversity
        'lexical_diversity',
        'lexical_diversity.lex_div',
        # spaCy collected
        *spacy_hidden,
        *en_hidden,
        # ctranslate2 + faster-whisper
        *ct2_hidden,
        *fw_hidden,
        # thinc / blis
        *thinc_hidden,
        *blis_hidden,
        # spaCy deps
        'cymem',
        'preshed',
        'murmurhash',
        'wasabi',
        'srsly',
        'catalogue',
        'typer',
        'confection',
        'langcodes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'test',
        # Exclude CUDA / GPU — app runs on CPU
        'torch',
        'torchvision',
        'tensorflow',
        # Large unused language data from wordfreq
        'wordfreq.language_info',
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
    console=False,       # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # set to 'icon.ico' if you add one
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
