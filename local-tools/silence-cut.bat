@echo off
chcp 65001 >nul
rem 무음 구간 자동 삭제. 인수 없이 실행하면 dB / 최소 길이 / 여백을 물어본다. 옵션: --help
python "%~dp0silence_cut.py" %*
pause
