#!/usr/bin/env python3
"""One-step launcher for MechDesign Agent.

    python start.py                 (Windows: double-click start.bat instead)
    python start.py --port 8080 --no-browser
    python start.py --reinstall     (rebuild the .venv folder from scratch)

The first run creates a private Python environment in ``.venv`` next to this
file and installs the app into it (a few minutes, needs internet). Later runs
start the web app straight away and open it in your browser. Press Ctrl+C to stop.
"""

# Keep this file free of newer syntax so that old Pythons reach the version check.
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if WINDOWS else "bin/python")
STAMP = VENV / ".mechdesign-install"
# The Anthropic SDK ([llm] extra) contains file paths about 165 characters long
# inside .venv. Windows refuses paths over 260 characters unless long paths are enabled.
MAX_FOLDER_CHARS_FOR_LLM = 90


def say(msg: str) -> None:
    print(f"[start] {msg}", flush=True)


def windows_long_paths_enabled() -> bool:
    try:
        import winreg

        key = r"SYSTEM\CurrentControlSet\Control\FileSystem"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            return winreg.QueryValueEx(k, "LongPathsEnabled")[0] == 1
    except (ImportError, OSError):
        return False


def choose_extras(explain: bool = True) -> str:
    if not WINDOWS or len(str(ROOT)) <= MAX_FOLDER_CHARS_FOR_LLM or windows_long_paths_enabled():
        return "llm,validation"
    if explain:
        say(f"This folder path is {len(str(ROOT))} characters long:")
        say(f"  {ROOT}")
        say("Windows cannot install the optional LLM assistant this deep, so it is skipped.")
        say("The app works fully; the assistant uses the rule-based parser instead.")
        say(r"To enable the LLM assistant, move the folder somewhere short, e.g. C:\code\mechdesign-agent,")
        say("and start it again.")
    return "validation"


def venv_works() -> bool:
    if not VENV_PYTHON.exists():
        return False
    try:
        return subprocess.run([str(VENV_PYTHON), "-c", "import sys"], capture_output=True).returncode == 0
    except OSError:
        return False


def install() -> None:
    """Install (again) only when the extras, the folder location or pyproject.toml changed."""
    extras = choose_extras(explain=False)
    pyproject = hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest()
    want = f"{extras}|{ROOT}|{pyproject}"  # the folder matters: the install points at ROOT/src
    if STAMP.exists() and STAMP.read_text(encoding="utf-8") == want:
        return
    choose_extras(explain=True)  # say once, at install time, if the LLM extra has to be skipped
    say(f"Installing MechDesign Agent and its dependencies (extras: {extras}). This can take a few minutes...")
    cmd = [str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-e", f".[{extras}]"]
    subprocess.run(cmd, cwd=ROOT, check=True)
    STAMP.write_text(want, encoding="utf-8")


def main() -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 - the launcher may be run by any Python
        say(f"MechDesign Agent needs Python 3.10 or newer; this is Python {sys.version.split()[0]}.")
        say("Download a current version from https://www.python.org/downloads/")
        return 1

    ap = argparse.ArgumentParser(description="Set up (first run) and start the MechDesign Agent web app.")
    ap.add_argument("--port", type=int, help="port for the web app (default 8000)")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    ap.add_argument("--reinstall", action="store_true", help="delete .venv and install again")
    args = ap.parse_args()

    if args.reinstall and VENV.exists():
        say("Removing the old .venv folder...")
        shutil.rmtree(VENV)
    if VENV.exists() and not venv_works():
        say("The .venv folder does not work on this computer (was it copied from another one?).")
        say("Run again with --reinstall to rebuild it.")
        return 1

    try:
        if not VENV.exists():
            say(f"First run: creating a private Python environment in {VENV}")
            venv.EnvBuilder(with_pip=True).create(VENV)
        install()
    except (subprocess.CalledProcessError, OSError) as exc:
        say(f"Setup failed: {exc}")
        say("Check your internet connection, then run: python start.py --reinstall")
        return 1

    cmd = [str(VENV_PYTHON), "-m", "mechdesign", "serve"]
    if args.port:
        cmd += ["--port", str(args.port)]
    if not args.no_browser:
        cmd.append("--open")
    say(f"Starting the web app at http://127.0.0.1:{args.port or 8000}  (press Ctrl+C to stop)")
    try:
        return subprocess.call(cmd, cwd=ROOT)  # cwd = ROOT so a .env file here is picked up
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
