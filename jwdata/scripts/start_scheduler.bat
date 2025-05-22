@echo off
cd /d %~dp0
call ..\venv\Scripts\activate.bat
start /B pythonw scheduler.py > ..\logs\scheduler.log 2>&1 