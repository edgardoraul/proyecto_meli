@echo off
cd /d "%~dp0"

:: Comprueba si los módulos ya existen en el sistema
py -c "import requests, dotenv" >nul 2>&1

:: Si falta alguno (errorlevel != 0), instala lo del requirements.txt
if %errorlevel% neq 0 (
    echo Instalando dependencias faltantes por primera vez...
    py -m pip install -r requirements.txt
)

:: Ejecuta el programa principal
py main.py