@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0scripts\publication_center.py"
    exit /b
)
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0scripts\publication_center.py"
    exit /b
)
python "%~dp0scripts\publication_center.py"
if errorlevel 1 pause
