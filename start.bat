@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro "python" en el PATH. Instala Python 3.10+ y vuelve a intentar.
    pause
    exit /b 1
)

echo Asistente de capturas de estudio
echo ---------------------------------
echo Si es la primera vez, instala las dependencias con:
echo   pip install -r asistente_capturas\requirements.txt
echo.

python "asistente_capturas\asistente_capturas.py"

echo.
echo El programa termino o se cerro. Revisa los mensajes de arriba si algo fallo.
pause
