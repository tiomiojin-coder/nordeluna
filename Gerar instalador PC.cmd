@echo off
cd /d "%~dp0"
python scripts\build-pc-installer.py %*
if errorlevel 1 echo Falha ao gerar o instalador. Confira a mensagem acima.
pause
