# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

project_root = Path.cwd()
resources_dir = project_root / "resources"

datas = []
if resources_dir.exists():
    datas.append((str(resources_dir), "resources"))

hiddenimports = [
    "keyring.backends",
    "mysql.connector",
    "psycopg2",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tablefree",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name="tablefree.app",
    icon=None,
    bundle_identifier="com.tablefree.app",
) if sys.platform == "darwin" else None

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="tablefree",
)
