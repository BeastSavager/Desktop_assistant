# PyInstaller spec — builds a single-file Jarvis.exe that runs the web app.
# Build with:  pyinstaller jarvis.spec --noconfirm   (or run build_exe.bat)

from PyInstaller.utils.hooks import collect_submodules

# uvicorn loads its loops/protocols dynamically; pull them all in. The web/file
# tool deps are imported lazily inside functions, so list them explicitly too.
hiddenimports = collect_submodules("uvicorn") + [
    "bs4",
    "httpx",
    "pypdf",
    "docx",
    "ddgs",
    "multipart",
    "anyio",
]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[("webapp", "webapp")],  # bundle the SPA next to the code
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Desktop/voice deps are not used by the web app — exclude to slim the exe.
    excludes=["PyQt5", "pygame", "pyaudio", "speech_recognition", "edge_tts"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
