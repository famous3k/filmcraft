@echo off
rem Start FilmCraft with the control channel on port 9876 (the local tools talk to the app through it).
start "" "%~dp0..\target\release\filmcraft.exe" --control 9876 %*
