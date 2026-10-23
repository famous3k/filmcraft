@echo off
rem FilmCraft 를 컨트롤 채널(포트 9876)과 함께 실행한다. 무음 삭제 / Whisper 자막 도구는 이 포트로 앱에 명령을 보낸다.
start "" "%~dp0..\target\release\filmcraft.exe" --control 9876 %*
