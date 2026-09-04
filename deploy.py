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
BACKFILL_SRC = SCRIPT_DIR / 'backfill_cli.py'

# The wrapper is a Python script with this shebang. The real Devin binary is an
# ELF/Mach-O executable. This distinguishes "wrapper installed" from "update
# overwrote the wrapper with a fresh real binary".
_WRAPPER_SHEBANG = b'#!/usr/bin/env python3'


def _real_home() -> Path:
    """Best-effort real user home, even when invoked as root via sudo/systemd.

    sudo resets HOME to /root and systemd services run as root, so Path.home()
    would point at the wrong place. Prefer SUDO_USER's passwd entry, then a
    non-/root HOME (set by the heal service), then fall back to Path.home().
    """
    if os.geteuid() != 0:
        return Path.home()
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        import pwd
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    env_home = os.environ.get('HOME')
    if env_home and env_home != '/root':
        return Path(env_home)
    return Path.home()


def _is_wrapper(path: Path) -> bool:
    """True if the file at path is the DevinTrack Python wrapper."""
    try:
        with open(path, 'rb') as f:
            return f.read(len(_WRAPPER_SHEBANG)) == _WRAPPER_SHEBANG
    except OSError:
        return False


def _files_equal(a: Path, b: Path) -> bool:
    """True if two files are byte-identical (size + content)."""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        import filecmp
        return filecmp.cmp(str(a), str(b), shallow=False)
    except OSError:
        return False


def find_devin_bin_dir() -> Path:
    """Find the directory containing the Devin Desktop binary (legacy single-target)."""
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
            _real_home() / '.local' / 'bin',
        ]
        bin_name = 'devin'
    else:  # Linux
        candidates = [
            Path('/usr/share/devin-desktop/resources/app/extensions/windsurf/devin/bin'),
            _real_home() / '.local' / 'bin',
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


def find_cli_bin_dir() -> Path | None:
    """Resolve the Devin CLI's active binary directory, or None if not installed.

    The CLI lays out versions under ~/.local/share/devin/cli/_versions/<ver>/bin/devin
    with a 'current' symlink pointing at the active version. We resolve the symlink
    chain to the real on-disk directory so the wrapper and its devin.real backup
    land next to the actual binary. This survives 'current' repoints on update:
    a new version dir gets wrapped by the next heal run.
    """
    base = _real_home() / '.local' / 'share' / 'devin' / 'cli' / '_versions' / 'current'
    devin = base / 'bin' / 'devin'
    if devin.is_file():
        real = devin.resolve()
        if real.name == 'devin':
            return real.parent
    return None


def find_devin_bin_dirs() -> list:
    """Return every Devin binary dir to wrap: Desktop (if present) + CLI (if present).

    Deduped by resolved path. On a Desktop-less host this still returns the CLI
    dir so CLI-only setups are tracked. DEVIN_TRACK_TARGETS (comma-separated
    'desktop','cli') restricts the set, so the user can wrap just the CLI
    without root, then run a full sudo pass for the Desktop separately.
    """
    wanted = {t.strip().lower() for t in os.environ.get('DEVIN_TRACK_TARGETS', '').split(',') if t.strip()} or {'desktop', 'cli'}
    dirs = []
    if 'desktop' in wanted:
        try:
            desktop = find_devin_bin_dir()
            if desktop:
                dirs.append(desktop)
        except SystemExit:
            pass
    if 'cli' in wanted:
        cli = find_cli_bin_dir()
        if cli and cli not in dirs:
            dirs.append(cli)
    return dirs


def deploy():
    if not WRAPPER_SRC.is_file():
        print(f'ERROR: wrapper not found at {WRAPPER_SRC}', file=sys.stderr)
        sys.exit(1)

    system = platform.system()

    if system == 'Windows':
        bin_dir = find_devin_bin_dir()
        _deploy_windows(bin_dir)
        print(f'\nWrapper installed in: {bin_dir}')
        print('Restart Devin Desktop to start using the tracker.')
        print(f'\nDashboard: python3 {SCRIPT_DIR / "dashboard" / "server.py"}')
        return

    # Unix: wrap every discovered Devin binary (Desktop + CLI).
    targets = find_devin_bin_dirs()
    if not targets:
        print('ERROR: no Devin binary found to wrap.', file=sys.stderr)
        sys.exit(1)
    for bin_dir in targets:
        print(f'\n--- target: {bin_dir} ---')
        _deploy_unix(bin_dir)
    print(f'\nWrapper installed in: {[str(t) for t in targets]}')
    print('Restart Devin Desktop / CLI sessions to start using the tracker.')
    print(f'\nDashboard: python3 {SCRIPT_DIR / "dashboard" / "server.py"}')


def _deploy_unix(bin_dir: Path):
    devin_path = bin_dir / 'devin'
    backup_path = bin_dir / 'devin.real'

    if not devin_path.exists():
        print(f'ERROR: {devin_path} not found', file=sys.stderr)
        sys.exit(1)

    if _is_wrapper(devin_path):
        # Wrapper already installed. Keep the existing devin.real backup; just
        # refresh the wrapper source in case DevinTrack itself was updated.
        if not backup_path.exists():
            print(f'WARNING: wrapper present but {backup_path} missing. '
                  f'The wrapper will fall back to PATH/ENV to find the real binary.',
                  file=sys.stderr)
        # Skip the copy if the installed wrapper is already byte-identical to
        # the source. This prevents re-triggering file watchers (e.g. the
        # systemd path unit) in an infinite loop when heal runs repeatedly.
        if _files_equal(WRAPPER_SRC, devin_path):
            print(f'Wrapper already current; no changes needed.')
            return
        print(f'Wrapper already installed; refreshing wrapper source only.')
    else:
        # devin is a real binary (either fresh install, or a Devin update
        # overwrote the wrapper). Back it up so the wrapper can exec it.
        # Skip the copy if the backup is already byte-identical (avoids
        # unnecessary writes and path-unit re-trigger on devin.real).
        if backup_path.exists() and _files_equal(devin_path, backup_path):
            print(f'Backup already current at {backup_path}.')
        else:
            print(f'Backing up real binary: {devin_path} -> {backup_path}')
            shutil.copy2(devin_path, backup_path)

    print(f'Installing wrapper: {WRAPPER_SRC} -> {devin_path}')
    # Atomic replace via temp file + rename. A direct copy2 fails with
    # "Text file busy" (ETXTBSY) if the binary is currently executing (e.g.
    # a live 'devin acp' process). os.rename over the target works: the
    # running process keeps the old (now-unlinked) inode; new invocations
    # get the new file. Temp file must be in the same directory for rename
    # to be atomic (same filesystem).
    import tempfile
    fd, tmp_name = tempfile.mkstemp(
        prefix='.devin-track-', suffix='.tmp', dir=str(bin_dir)
    )
    os.close(fd)
    try:
        shutil.copy2(WRAPPER_SRC, tmp_name)
        os.chmod(tmp_name, 0o755)
        os.rename(tmp_name, devin_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    # If running as root, match the wrapper + backup ownership to the target
    # directory's owner. Keeps CLI version-dir files user-owned (so the CLI's
    # own version cleanup can remove them) while Desktop files stay root-owned.
    if os.geteuid() == 0:
        st = os.stat(bin_dir)
        try:
            os.chown(devin_path, st.st_uid, st.st_gid)
            if backup_path.exists():
                os.chown(backup_path, st.st_uid, st.st_gid)
        except OSError:
            pass

    # Install / refresh the backfill helper so the wrapper can import from the
    # same directory after deployment.
    if BACKFILL_SRC.is_file():
        backfill_dest = bin_dir / 'backfill_cli.py'
        if not backfill_dest.exists() or not _files_equal(BACKFILL_SRC, backfill_dest):
            print(f'Installing backfill helper: {BACKFILL_SRC} -> {backfill_dest}')
            shutil.copy2(BACKFILL_SRC, backfill_dest)
            if os.geteuid() == 0:
                try:
                    os.chown(backfill_dest, st.st_uid, st.st_gid)
                except OSError:
                    pass


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


def _undeploy_unix(bin_dir: Path):
    backup = bin_dir / 'devin.real'
    devin_path = bin_dir / 'devin'

    if not _is_wrapper(devin_path):
        # The wrapper is not installed (Devin update already replaced it
        # with a real binary). Restoring the stale backup would downgrade
        # Devin. Nothing to undeploy.
        if backup.exists():
            print(f'Wrapper not installed at {devin_path} (real binary). '
                  f'A stale backup exists at {backup}; leaving it in place '
                  f'to avoid downgrading the current Devin.')
        else:
            print(f'Wrapper not installed at {devin_path}; nothing to undeploy.')
        return

    if not backup.exists():
        print(f'ERROR: No backup found at {backup}', file=sys.stderr)
        return

    print(f'Restoring: {backup} -> {devin_path}')
    shutil.move(str(backup), str(devin_path))
    os.chmod(devin_path, 0o755)


def undeploy():
    system = platform.system()

    if system == 'Windows':
        bin_dir = find_devin_bin_dir()
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
        print('Original Devin binary restored.')
        return

    # Unix: restore every wrapped target (Desktop + CLI).
    targets = find_devin_bin_dirs()
    if not targets:
        print('ERROR: no Devin binary found to undeploy.', file=sys.stderr)
        sys.exit(1)
    for bin_dir in targets:
        print(f'\n--- target: {bin_dir} ---')
        _undeploy_unix(bin_dir)
    print('\nOriginal Devin binary(ies) restored.')


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
