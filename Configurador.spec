# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('backend/.env.example', '.'),
    ('frontend/assets/app_icon.ico', 'frontend/assets'),
]
binaries = []
hiddenimports = [
    'asyncpg', 'asyncpg.protocol', 'fdb',
    'sqlalchemy', 'sqlalchemy.dialects.postgresql',
]

excludes = [
    'matplotlib', 'scipy', 'pandas', 'sklearn', 'tkinter',
    'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
    'PySide6.QtWebChannel', 'PySide6.QtPositioning',
    'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtQuickWidgets',
    'PySide6.QtCharts', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
    'PySide6.QtPrintSupport', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
    'PySide6.QtDataVisualization', 'PySide6.QtGraphs',
    'PySide6.QtHttpServer', 'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets', 'PySide6.QtNetwork',
    'PySide6.QtNfc', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
    'PySide6.QtRemoteObjects', 'PySide6.QtSensors',
    'PySide6.QtSerialPort', 'PySide6.QtSpace',
    'PySide6.QtSpeech', 'PySide6.QtTest', 'PySide6.QtTextToSpeech',
    'PySide6.QtUiTools', 'PySide6.QtVirtualKeyboard',
    'PySide6.QtXml', 'PySide6.Qt3D*',
    'numpy', 'PIL', 'lxml', 'cryptography',
    'uvicorn', 'fastapi', 'httpx', 'certifi', 'charset_normalizer',
    'jose', 'python_jose',
    'watchdog', 'pymupdf', 'fitz',
]

a = Analysis(
    ['configurador\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ECOnnectConfigurador',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
