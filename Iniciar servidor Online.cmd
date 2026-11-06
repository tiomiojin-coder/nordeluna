@echo off
setlocal
cd /d "%~dp0"
python server\start.py
if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar. Confira se Python esta instalado e se a porta 8765 ja esta em uso.
    pause
)
