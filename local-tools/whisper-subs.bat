@echo off
chcp 65001 >nul
rem Whisper large-v3 로 현재 시퀀스의 한국어 자막을 만들어 자막 트랙으로 가져온다. 옵션: --help
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo 먼저 setup.ps1 을 한 번 실행하세요:  powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0whisper_subs.py" %*
pause
