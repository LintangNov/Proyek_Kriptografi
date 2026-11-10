# Build: npm run build, lalu pyinstaller --noconfirm --clean aegisvault.spec
# Hasil: dist/AegisVault.exe. dev-mock.js sengaja tidak ikut, jadi .exe selalu memakai backend asli.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("frontend/index.html", "frontend"),
    ("frontend/app.js", "frontend"),
    ("frontend/assets", "frontend/assets"),
]
datas += collect_data_files("cv2", includes=["data/*.xml"])

# jpeglib mencari cjpeglib_*.pyd di foldernya sendiri lalu memuatnya lewat ctypes,
# jadi PyInstaller tidak menemukannya sendiri.
import glob
import os
import jpeglib

_cjpeg = os.path.join(os.path.dirname(jpeglib.__file__), "cjpeglib")
binaries = [(f, "jpeglib/cjpeglib") for f in glob.glob(os.path.join(_cjpeg, "cjpeglib_*.pyd"))]
hiddenimports = collect_submodules("uvicorn") + collect_submodules("jpeglib") + ["python_multipart", "clr"]

a = Analysis(
    ["main.py"],
    datas=datas,
    binaries=binaries,
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
