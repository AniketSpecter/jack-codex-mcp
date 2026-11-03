@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Run setup.ps1 first. See docs\INSTALL.md.
  pause
  exit /b 1
)
start "JACK Codex MCP" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0workspace.py"
