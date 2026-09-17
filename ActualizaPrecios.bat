@echo off
cd /d "%~dp0"

:: Verifica dependencias para lectura de Excel (.xls y .xlsx)
py -c "import pandas, xlrd, openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo Instalando librerias para lectura de Excel...
    py -m pip install pandas xlrd openpyxl
)

py Pricer.py