@echo off
setlocal enabledelayedexpansion

:: Resolve script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "FLAG_FILE=isInstalled"

:: Controllo se il file flag esiste
if exist "%SCRIPT_DIR%%FLAG_FILE%" (
    echo Il file '%FLAG_FILE%' e' presente. Avvio del programma...

    if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
        start "" "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%app.py"
    ) else (
        start "" python "%SCRIPT_DIR%app.py"
    )
) else (
    echo Il file '%FLAG_FILE%' non esiste. Avvio procedura di installazione...
    
    :: Configurazione ambiente virtuale Python e dipendenze
    python -m venv "%SCRIPT_DIR%.venv"
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    python -m pip install -r "%SCRIPT_DIR%requirements.txt"
    
    type nul > "%SCRIPT_DIR%%FLAG_FILE%"
    echo Installazione completata con successo
    echo Modifica config.json e riavvia il programma
)