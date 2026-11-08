@echo off
cd /d "%~dp0"
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)"') do start "" "%%~dpPpythonw.exe" "%~dp0scripts\moderation-manager.py"
