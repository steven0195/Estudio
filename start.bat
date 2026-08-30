@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro "python" en el PATH. Instala Python 3.10+ y vuelve a intentar.
    pause
    exit /b 1
)

:menu
cls
echo Asistente de estudio
echo =====================
echo   1. Capturas de pantalla (atajo de teclado + LM Studio)
echo   2. Transcriptor de documentos (.txt/.pdf/.docx/.pptx/.doc a Markdown)
echo   3. Solucionador de actividades (borrador punto por punto, con RAG)
echo   4. Nueva unidad (crea el esqueleto de carpetas y archivos base)
echo   5. Instalar/actualizar dependencias
echo   0. Salir
echo.
set "opcion="
set /p opcion="Elige una opcion: "

if "%opcion%"=="1" goto capturas
if "%opcion%"=="2" goto transcriptor
if "%opcion%"=="3" goto solucionador
if "%opcion%"=="4" goto nueva_unidad
if "%opcion%"=="5" goto instalar
if "%opcion%"=="0" goto fin
echo.
echo Opcion invalida.
pause
goto menu

:capturas
python "asistente_estudio\capturas.py"
pause
goto menu

:transcriptor
set "ruta="
set /p ruta="Ruta del archivo o carpeta a transcribir: "
if "%ruta%"=="" goto menu
python "asistente_estudio\transcriptor_documentos.py" "%ruta%"
pause
goto menu

:solucionador
set "ruta="
set /p ruta="Ruta del archivo de actividad: "
if "%ruta%"=="" goto menu
python "asistente_estudio\solucionador_actividades.py" "%ruta%"
pause
goto menu

:nueva_unidad
set "ruta="
set /p ruta="Ruta de la nueva unidad o tema (relativa a la raiz del repo): "
if "%ruta%"=="" goto menu
python "asistente_estudio\nueva_unidad.py" "%ruta%"
pause
goto menu

:instalar
python -m pip install -r "asistente_estudio\requirements.txt"
pause
goto menu

:fin
endlocal
