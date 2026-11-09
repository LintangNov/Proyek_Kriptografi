# Build: npm run build, lalu pyinstaller --noconfirm --clean aegisvault.spec
# Hasil: dist/AegisVault.exe. dev-mock.js sengaja tidak ikut, jadi .exe selalu memakai backend asli.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("frontend/index.html", "frontend"),
    ("frontend/app.js", "frontend"),
    ("frontend/assets", "frontend/assets"),
]
datas += collect_data_files("cv2", includes=["data/*.xml"])

hiddenimports = collect_submodules("uvicorn") + ["python_multipart", "clr"]

a = Analysis(
    ["main.py"],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "matplotlib", "IPython", "PyQt5", "PyQt6", "PySide2", "PySide6"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="AegisVault",
    icon="assets/aegisvault.ico",
    console=False,
    upx=False,
)
