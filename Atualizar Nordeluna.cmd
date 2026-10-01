@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0scripts\nordeluna_updater.py"
    exit /b
)
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0scripts\nordeluna_updater.py"
    exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0scripts\nordeluna_updater.py"
    if errorlevel 1 pause
    exit /b
)
echo Instale Python 3.11 ou superior com Tcl/Tk e a opcao Add Python to PATH.
pause
