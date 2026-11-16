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
    # os.geteuid does not exist on Windows.
    if getattr(os, 'geteuid', lambda: -1)() != 0:
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
        candidates = _windows_bin_dirs()
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


def _windows_bin_dirs() -> list:
    """Directories that may contain devin.exe on Windows.

    Covers the T3 / Devin CLI tool layout (~/.t3/tools/devin/<ver>/<plat>/bin),
    the Devin CLI versioned layout under %APPDATA%, and Devin Desktop. Also
    consults PATH so a user-installed CLI is picked up.
    """
    dirs = []
    t3 = Path.home() / '.t3' / 'tools' / 'devin'
    if t3.is_dir():
        for ver in sorted(t3.iterdir(), reverse=True):
            for plat in ('windows-x86_64', 'windows-aarch64'):
                d = ver / plat / 'bin'
                if (d / 'devin.exe').is_file():
                    dirs.append(d)
    cli = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'devin' / 'cli' / '_versions'
    if cli.is_dir():
        for ver in cli.iterdir():
            d = ver / 'bin'
            if (d / 'devin.exe').is_file():
                dirs.append(d)
    found = shutil.which('devin.exe')
    if found:
        d = Path(found).parent
        if d not in dirs:
            dirs.append(d)
    dirs.append(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Devin Desktop' / 'resources' / 'app' / 'extensions' / 'windsurf' / 'devin' / 'bin')
    dirs.append(Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Devin Desktop' / 'resources' / 'app' / 'extensions' / 'windsurf' / 'devin' / 'bin')
    return dirs


def _windows_track_dir() -> Path:
    """Data dir used by the wrapper/server on Windows (%LOCALAPPDATA%\\devin_track)."""
    base = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
    return Path(base) / 'devin_track'


_LAUNCHER_CS = r'''
// DevinTrack devin.exe launcher: a real PE binary standing in for the Devin
// CLI. Spawned in place of devin.exe by anything (absolute path, PATH, or a
// parent process), it runs the Python wrapper with the image path prepended
// — the same argv shape an IFEO Debugger would produce — so the wrapper's
// single code path handles interception, logging and pass-through.
// {PYTHON_EXE} is substituted at deploy time with the detected interpreter.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;

static class DevinTrackLauncher
{
    static int Main(string[] args)
    {
        string dir = Path.GetDirectoryName(
            System.Reflection.Assembly.GetExecutingAssembly().Location);
        string self = Path.Combine(dir, "devin.exe");
        string wrapper = Path.Combine(dir, "devin_wrapper.py");
        if (!File.Exists(wrapper))
        {
            Console.Error.WriteLine("DevinTrack: devin_wrapper.py not found next to devin.exe");
            return 1;
        }

        var argv = new StringBuilder();
        argv.Append('"').Append(wrapper).Append("\" \"").Append(self).Append('"');
        foreach (string a in args)
        {
            argv.Append(' ');
            // Canonical CreateProcess quoting: backslashes only need doubling
            // immediately before a quote or at the end of the argument.
            int bs = 0;
            argv.Append('"');
            for (int i = 0; i < a.Length; i++)
            {
                if (a[i] == '\\') { bs++; continue; }
                if (a[i] == '"') argv.Append('\\', bs * 2 + 1).Append('"');
                else argv.Append('\\', bs).Append(a[i]);
                bs = 0;
            }
            argv.Append('\\', bs * 2).Append('"');
        }

        string[] pythons = { @"{PYTHON_EXE}", "python.exe", "py.exe", "python3.exe" };
        foreach (string py in pythons)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = py,
                    Arguments = argv.ToString(),
                    UseShellExecute = false,
                };
                // std handles are inherited by default, so ACP's stdin/stdout
                // JSON-RPC flows through the launcher untouched.
                var p = Process.Start(psi);
                p.WaitForExit();
                return p.ExitCode;
            }
            catch (System.ComponentModel.Win32Exception) { /* not found -> next */ }
        }
        Console.Error.WriteLine("DevinTrack: no Python interpreter found for the wrapper");
        return 1;
    }
}
'''


def _find_csc() -> str | None:
    """Locate the .NET Framework C# compiler shipped with Windows."""
    windir = os.environ.get('WINDIR', r'C:\Windows')
    for rel in (
        r'Microsoft.NET\Framework64\v4.0.30319\csc.exe',
        r'Microsoft.NET\Framework\v4.0.30319\csc.exe',
    ):
        p = Path(windir) / rel
        if p.is_file():
            return str(p)
    return None


def _compile_launcher(bin_dir: Path) -> bool:
    """Compile devin_launcher.cs -> devin.exe in bin_dir. False when no compiler."""
    csc = _find_csc()
    if not csc:
        return False
    cs_path = bin_dir / 'devin_launcher.cs'
    cs_path.write_text(
        _LAUNCHER_CS.replace('{PYTHON_EXE}', sys.executable), encoding='utf-8'
    )
    import subprocess
    r = subprocess.run(
        [csc, '/nologo', '/target:exe', '/platform:anycpu',
         f'/out:{bin_dir / "devin.exe"}', str(cs_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f'ERROR: csc failed:\n{r.stdout}\n{r.stderr}', file=sys.stderr)
        return False
    return True


def find_cli_bin_dir() -> Path | None:
    """Resolve the Devin CLI's active binary directory, or None if not installed.

    The CLI lays out versions under ~/.local/share/devin/cli/_versions/<ver>/bin/devin
    with a 'current' symlink pointing at the active version. We resolve the symlink
    chain to the real on-disk directory so the wrapper and its devin.real backup
    land next to the actual binary. This survives 'current' repoints on update:
    a new version dir gets wrapped by the next heal run.
    """
    if platform.system() == 'Windows':
        for d in _windows_bin_dirs():
            return d  # newest T3/CLI/Desktop dir with devin.exe
        return None
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
        bin_dirs = _windows_bin_dirs()
        if not bin_dirs:
            print('ERROR: devin.exe not found in any known location.', file=sys.stderr)
            print('Set DEVIN_BIN_DIR to override.', file=sys.stderr)
            sys.exit(1)
        wrapped = []
        for d in bin_dirs:
            if _deploy_windows(d):
                wrapped.append(d)
        if wrapped:
            print(f'\nWrapper installed for: {[str(d) for d in wrapped]}')
            print('Restart Devin Desktop / CLI sessions to start using the tracker.')
        else:
            print('\nNothing was wrapped (no compiler or no binary found).')
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


def _is_launcher(exe: Path) -> bool:
    """True if exe is the DevinTrack launcher, not the real Devin binary.

    The compiled launcher is a few KB .NET stub; the real CLI is tens of MB.
    The marker string embedded in the assembly makes the check precise.
    """
    try:
        if exe.stat().st_size > 1_000_000:
            return False
        return b'DevinTrackLauncher' in exe.read_bytes()
    except OSError:
        return False


def _deploy_windows(bin_dir: Path) -> bool:
    """Wrap devin.exe in bin_dir with the compiled launcher. Returns wrapped."""
    devin_exe = bin_dir / 'devin.exe'
    backup_exe = bin_dir / 'devin.exe.bak'
    wrapper_py = bin_dir / 'devin_wrapper.py'
    cmd_shim = bin_dir / 'devin.cmd'

    if not devin_exe.exists():
        print(f'SKIP: {devin_exe} not found')
        return False

    # The wrapper script must exist next to the launcher either way.
    print(f'Installing wrapper: {WRAPPER_SRC} -> {wrapper_py}')
    shutil.copy2(WRAPPER_SRC, wrapper_py)
    track = _windows_track_dir()
    track.mkdir(parents=True, exist_ok=True)
    if BACKFILL_SRC.is_file():
        for dest in (bin_dir / 'backfill_cli.py', track / 'backfill_cli.py'):
            if not _files_equal(BACKFILL_SRC, dest):
                shutil.copy2(BACKFILL_SRC, dest)

    if _is_launcher(devin_exe):
        if backup_exe.exists():
            print(f'Wrapper already installed at {devin_exe}; refreshed wrapper script.')
            return True
        print(f'WARNING: launcher present but {backup_exe} missing; re-creating '
              f'backup from the real binary is impossible without it. '
              f'Run `devin update` first or reinstall Devin.', file=sys.stderr)
        return False

    if not _find_csc():
        print(f'SKIP: csc.exe not found; cannot build devin.exe launcher for {bin_dir}',
              file=sys.stderr)
        print('       Install .NET Framework 4.x (bundled with Windows) or wrap manually.',
              file=sys.stderr)
        return False

    # Move the real binary aside (rename works even while it is running),
    # then put the compiled launcher at devin.exe. Any caller — absolute path
    # or PATH — now reaches the wrapper.
    print(f'Moving real binary aside: {devin_exe} -> {backup_exe}')
    os.replace(devin_exe, backup_exe)
    try:
        if not _compile_launcher(bin_dir):
            os.replace(backup_exe, devin_exe)  # restore
            return False
    except Exception:
        try:
            os.replace(backup_exe, devin_exe)
        except OSError:
            pass
        raise
    print(f'Compiled launcher: {devin_exe}')

    # A .cmd shim stays as a convenience for extensionless `devin` calls.
    cmd_content = f'''@echo off
"{sys.executable}" "%~dp0devin_wrapper.py" %*
'''
    if not cmd_shim.exists() or cmd_shim.read_text(encoding='utf-8') != cmd_content:
        print(f'Installing CMD shim: {cmd_shim}')
        cmd_shim.write_text(cmd_content, encoding='utf-8')
    return True


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
        for d in _windows_bin_dirs():
            devin_exe = d / 'devin.exe'
            backup = d / 'devin.exe.bak'
            if _is_launcher(devin_exe):
                if backup.exists():
                    print(f'Restoring: {backup} -> {devin_exe}')
                    os.replace(backup, devin_exe)
                else:
                    print(f'WARNING: launcher at {devin_exe} but no backup; '
                          f'removing launcher (run `devin update` to reinstall the CLI)',
                          file=sys.stderr)
                    devin_exe.unlink()
            for name in ('devin_wrapper.py', 'devin.cmd', 'devin_launcher.cs',
                         'backfill_cli.py', 'devin.exe.bak'):
                f = d / name
                if f.exists():
                    f.unlink()
                    print(f'Removed {f}')
        track = _windows_track_dir()
        for name in ('devin_wrapper.py', 'backfill_cli.py'):
            f = track / name
            if f.exists():
                f.unlink()
                print(f'Removed {f}')
        print('\nOriginal devin.exe restored; wrapper files removed.')
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
