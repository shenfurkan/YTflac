"""
YtFLAC build script.

Usage:
    python build.py              # build onefile EXE
    python build.py --onedir     # build folder bundle (faster startup)
    python build.py --installer  # also compile Inno Setup installer (needs ISCC.exe in PATH)
    python build.py --clean      # remove build/, dist/, *.spec, installer/ and exit
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "YtFLAC"
ENTRY = ROOT / "ytflac" / "__main__.py"
ICON = ROOT / "images" / "ytflaclogo.ico"
ISS_FILE = ROOT / f"{APP_NAME}.iss"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
INSTALLER_DIR = ROOT / "installer"
SPEC_FILE = ROOT / f"{APP_NAME}.spec"


def _log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def clean() -> None:
    for p in (BUILD_DIR, DIST_DIR, INSTALLER_DIR):
        if p.exists():
            _log(f"rm -rf {p.relative_to(ROOT)}")
            shutil.rmtree(p, ignore_errors=True)
    if SPEC_FILE.exists():
        _log(f"rm {SPEC_FILE.name}")
        SPEC_FILE.unlink(missing_ok=True)
    pycache = list(ROOT.rglob("__pycache__"))
    for p in pycache:
        shutil.rmtree(p, ignore_errors=True)
    _log("clean done")


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        _log("PyInstaller missing, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_exe(onefile: bool = True) -> Path:
    if not ENTRY.exists():
        raise FileNotFoundError(f"Entry point not found: {ENTRY}")
    if not ICON.exists():
        raise FileNotFoundError(f"Icon not found: {ICON}")

    ensure_pyinstaller()

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--windowed",
        "--icon",
        str(ICON),
        "--add-data",
        f"images{';' if sys.platform == 'win32' else ':'}images",
    ]
    if onefile:
        args.append("--onefile")
    args.append(str(ENTRY))

    _log(" ".join(args[2:]))
    subprocess.check_call(args, cwd=ROOT)

    exe_name = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
    if onefile:
        exe_path = DIST_DIR / exe_name
    else:
        exe_path = DIST_DIR / APP_NAME / exe_name

    if not exe_path.exists():
        raise RuntimeError(f"Build finished but EXE not found at {exe_path}")
    _log(f"EXE built: {exe_path}")
    return exe_path


def build_installer() -> Path:
    if not ISS_FILE.exists():
        raise FileNotFoundError(f"Inno Setup script not found: {ISS_FILE}")
    iscc = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if not iscc:
        raise RuntimeError(
            "ISCC.exe not found in PATH. Install Inno Setup 6 and ensure ISCC.exe is on PATH."
        )

    INSTALLER_DIR.mkdir(exist_ok=True)
    _log(f"compiling installer: {ISS_FILE.name}")
    subprocess.check_call([iscc, str(ISS_FILE)], cwd=ROOT)

    # Output filename comes from .iss (OutputBaseFilename)
    out = next(INSTALLER_DIR.glob("*.exe"), None)
    if out is None:
        raise RuntimeError("Installer build finished but no .exe was produced.")
    _log(f"Installer built: {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="YtFLAC build helper")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build folder bundle instead of single file",
    )
    parser.add_argument(
        "--installer", action="store_true", help="Also compile the Inno Setup installer"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Remove build artifacts and exit"
    )
    args = parser.parse_args()

    if args.clean:
        clean()
        return 0

    try:
        build_exe(onefile=not args.onedir)
        if args.installer:
            build_installer()
    except Exception as exc:
        _log(f"ERROR: {exc}")
        return 1

    _log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
