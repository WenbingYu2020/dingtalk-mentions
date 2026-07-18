# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — DingTalkMentions GUI
运行方式（在项目根目录下）：
    pyinstaller --noconfirm DingTalkMentions.spec
输出：
    dist/DingTalkMentions.exe
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT_ROOT / 'gui' / 'app.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'gui' / 'dws_helper.py'), 'gui'),
        (str(PROJECT_ROOT / 'gui' / 'dws_installer.py'), 'gui'),
        (str(PROJECT_ROOT / 'gui' / 'datetime_picker.py'), 'gui'),
        (str(PROJECT_ROOT / 'core'), 'core'),
    ],
    hiddenimports=[
        'core',
        'core.paths',
        'core.dws',
        'core.state',
        'core.logging_setup',
        'core.table_setup',
        'core.fetcher',
        'gui.dws_helper',
        'gui.dws_installer',
        'gui.datetime_picker',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='DingTalkMentions',
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
    icon=str(PROJECT_ROOT / 'assets' / 'icon.ico'),
)
