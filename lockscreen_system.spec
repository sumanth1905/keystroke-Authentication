# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Common analysis settings
common_analysis = {
    'pathex': [],
    'binaries': [],
    'datas': [],
    'hiddenimports': [
        'sklearn.neighbors._partition_nodes',
        'sklearn.utils._cython_blas',
        'sklearn.utils._weight_vector',
        'sklearn.neighbors._typedefs',
        'sklearn.metrics.pairwise',
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'win32file',
        'win32event',
        'winshell',
        'psutil',
        'tkinter'
    ],
    'hookspath': [],
    'hooksconfig': {},
    'runtime_hooks': [],
    'excludes': [],
    'win_no_prefer_redirects': False,
    'win_private_assemblies': False,
    'cipher': block_cipher,
    'noarchive': False,
}

# Add direct file copies for additional files
added_files = [
    ('0.bat', '0.bat', 'DATA'),
    ('launcher.vbs', 'launcher.vbs', 'DATA'),
    ('lock.ico', 'lock.ico', 'DATA'),
]

# Define the splash screen application
splash_a = Analysis(
    ['splash.py'],
    **common_analysis
)
splash_a.datas += added_files
splash_pyz = PYZ(splash_a.pure, splash_a.zipped_data, cipher=block_cipher)
splash_exe = EXE(
    splash_pyz,
    splash_a.scripts,
    [],
    exclude_binaries=True,
    name='Entypt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lock.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Define the main setup application
train_auth_a = Analysis(
    ['train_auth.py'],
    **common_analysis
)
train_auth_a.datas += added_files
train_auth_pyz = PYZ(train_auth_a.pure, train_auth_a.zipped_data, cipher=block_cipher)
train_auth_exe = EXE(
    train_auth_pyz,
    train_auth_a.scripts,
    [],
    exclude_binaries=True,
    name='Training',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lock.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Define the lockscreen application
lockscreen_a = Analysis(
    ['lockscreen.py'],
    **common_analysis
)
lockscreen_pyz = PYZ(lockscreen_a.pure, lockscreen_a.zipped_data, cipher=block_cipher)
lockscreen_exe = EXE(
    lockscreen_pyz,
    lockscreen_a.scripts,
    [],
    exclude_binaries=True,
    name='Lockscreen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lock.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Define the check_unlock application
check_unlock_a = Analysis(
    ['check_unlock.py'],
    **common_analysis
)
check_unlock_pyz = PYZ(check_unlock_a.pure, check_unlock_a.zipped_data, cipher=block_cipher)
check_unlock_exe = EXE(
    check_unlock_pyz,
    check_unlock_a.scripts,
    [],
    exclude_binaries=True,
    name='CheckUnlock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lock.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect all binaries and other files into a single directory
coll = COLLECT(
    splash_exe,
    splash_a.binaries,
    splash_a.zipfiles,
    splash_a.datas,
    
    train_auth_exe,
    train_auth_a.binaries,
    train_auth_a.zipfiles,
    train_auth_a.datas,
    
    lockscreen_exe,
    lockscreen_a.binaries,
    lockscreen_a.zipfiles,
    lockscreen_a.datas,
    
    check_unlock_exe,
    check_unlock_a.binaries,
    check_unlock_a.zipfiles,
    check_unlock_a.datas,
    
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Entypt',
)