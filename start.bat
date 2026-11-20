@echo off
rem Double-click to start MechDesign Agent. The first run installs it into .venv (needs internet).
setlocal
cd /d "%~dp0"
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE where python >nul 2>nul && set "PYEXE=python"
if not defined PYEXE (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation, then double-click this file again.
  pause
  exit /b 1
)
%PYEXE% start.py %*
if errorlevel 1 pause
