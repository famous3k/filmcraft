@echo off
rem Remove silent parts of the open sequence. Without options it asks for dB / min length / padding. Options: --help
chcp 65001 >nul
python "%~dp0silence_cut.py" %*
pause
