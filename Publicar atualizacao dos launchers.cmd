@echo off
cd /d "%~dp0"
python scripts\finalize-client-release.py --publish %*
if errorlevel 1 echo Publicacao nao concluida. Confira a mensagem acima.
pause
