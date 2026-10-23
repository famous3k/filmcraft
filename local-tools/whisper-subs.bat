@echo off
rem Transcribe the open sequence with Whisper large-v3 and import it as a caption track. Options: --help
chcp 65001 >nul
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run setup first:  powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0whisper_subs.py" %*
pause
