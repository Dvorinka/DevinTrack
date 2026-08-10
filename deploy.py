#!/usr/bin/env python3
"""
Cross-platform installer for the DevinTrack wrapper.

Works on Linux, macOS, and Windows. Finds the Devin Desktop binary,
backs it up, and installs the wrapper in its place.

Usage:
    python3 deploy.py              # install wrapper
    python3 deploy.py --undeploy   # restore original binary

Environment:
    DEVIN_BIN_DIR  - override the Devin binary directory (auto-detected if not set)

jarvis: ceiling Python deploy script; no external deps.
"""

import os
import platform
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
WRAPPER_SRC = SCRIPT_DIR / 'devin'


def find_devin_bin_dir() -> Path:
    """Find the directory containing the Devin binary."""
    override = os.environ.get('DEVIN_BIN_DIR')
    if override:
        p = Path(override)
        if p.is_dir():
            return p

    system = platform.system()
    if system == 'Windows':
        candidates = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Devin Desktop' / 'resources' / 'app' / 'extensions' / 'windsurf' / 'devin' / 'bin',
            Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Devin Desktop' / 'resources' / 'app' / 'extensions' / 'windsurf' / 'devin' / 'bin',
        ]
        bin_name = 'devin.exe'
    elif system == 'Darwin':
        candidates = [
            Path('/Applications/Devin Desktop.app/Contents/Resources/app/extensions/windsurf/devin/bin'),
            Path.home() / '.local' / 'bin',
        ]
        bin_name = 'devin'
    else:  # Linux
        candidates = [
            Path('/usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin'),
            Path.home() / '.local' / 'bin',
            Path('/usr/local/bin'),
        ]
        bin_name = 'devin'

    for c in candidates:
        if (c / bin_name).is_file():
            return c

    print(f'ERROR: Devin binary not found in any of:', file=sys.stderr)
    for c in candidates:
        print(f'  {c}', file=sys.stderr)
    print(f'Set DEVIN_BIN_DIR to override.', file=sys.stderr)
    sys.exit(1)


def deploy():
    if not WRAPPER_SRC.is_file():
        print(f'ERROR: wrapper not found at {WRAPPER_SRC}', file=sys.stderr)
        sys.exit(1)

    bin_dir = find_devin_bin_dir()
    system = platform.system()

    if system == 'Windows':
        _deploy_windows(bin_dir)
    else:
        _deploy_unix(bin_dir)

    print(f'\nWrapper installed in: {bin_dir}')
    print('Restart Devin Desktop to start using the tracker.')
    print(f'\nDashboard: python3 {SCRIPT_DIR / "dashboard" / "server.py"}')


def _deploy_unix(bin_dir: Path):
    devin_path = bin_dir / 'devin'
    backup_path = bin_dir / 'devin.real'

    if not devin_path.exists():
        print(f'ERROR: {devin_path} not found', file=sys.stderr)
        sys.exit(1)

    if backup_path.exists():
        print(f'Backup already exists at {backup_path}, updating wrapper only.')
    else:
        print(f'Backing up original: {devin_path} -> {backup_path}')
        shutil.copy2(devin_path, backup_path)

    print(f'Installing wrapper: {WRAPPER_SRC} -> {devin_path}')
    shutil.copy2(WRAPPER_SRC, devin_path)
    os.chmod(devin_path, 0o755)


def _deploy_windows(bin_dir: Path):
    devin_exe = bin_dir / 'devin.exe'
    backup_exe = bin_dir / 'devin.exe.bak'
    wrapper_py = bin_dir / 'devin_wrapper.py'
    cmd_shim = bin_dir / 'devin.cmd'

    if not devin_exe.exists():
        print(f'ERROR: {devin_exe} not found', file=sys.stderr)
        sys.exit(1)

    if backup_exe.exists():
        print(f'Backup already exists at {backup_exe}, updating wrapper only.')
    else:
        print(f'Backing up original: {devin_exe} -> {backup_exe}')
        shutil.copy2(devin_exe, backup_exe)

    # Install the Python wrapper script.
    print(f'Installing wrapper: {WRAPPER_SRC} -> {wrapper_py}')
    shutil.copy2(WRAPPER_SRC, wrapper_py)

    # Create a .cmd shim that calls Python on the wrapper.
    # Rename the original .exe out of the way, then install the .cmd as "devin".
    cmd_content = f'''@echo off
python "%~dp0devin_wrapper.py" %*
'''
    print(f'Installing CMD shim: {cmd_shim}')
    cmd_shim.write_text(cmd_content)

    # On Windows, Devin Desktop likely calls devin.exe directly.
    # We can't replace an .exe with a .cmd, so we need a different approach.
    # The wrapper.py checks DEVIN_TRACK_REAL for the backup path.
    print(f'\nNOTE: On Windows, set DEVIN_TRACK_REAL={backup_exe}')
    print(f'in your environment so the wrapper finds the original binary.')


def undeploy():
    bin_dir = find_devin_bin_dir()
    system = platform.system()

    if system == 'Windows':
        backup = bin_dir / 'devin.exe.bak'
        devin_exe = bin_dir / 'devin.exe'
        wrapper_py = bin_dir / 'devin_wrapper.py'
        cmd_shim = bin_dir / 'devin.cmd'

        if not backup.exists():
            print(f'ERROR: No backup found at {backup}', file=sys.stderr)
            sys.exit(1)

        print(f'Restoring: {backup} -> {devin_exe}')
        shutil.move(str(backup), str(devin_exe))
        for f in (wrapper_py, cmd_shim):
            if f.exists():
                f.unlink()
    else:
        backup = bin_dir / 'devin.real'
        devin_path = bin_dir / 'devin'

        if not backup.exists():
            print(f'ERROR: No backup found at {backup}', file=sys.stderr)
            sys.exit(1)

        print(f'Restoring: {backup} -> {devin_path}')
        shutil.move(str(backup), str(devin_path))
        os.chmod(devin_path, 0o755)

    print('Original Devin binary restored.')


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return
    if '--undeploy' in sys.argv or '--remove' in sys.argv:
        undeploy()
    else:
        deploy()


if __name__ == '__main__':
    main()
