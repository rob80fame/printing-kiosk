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

    :: Lettura del parametro 'pass' da config.json tramite PowerShell
    set "POSTGRESQL_PASS="
    if exist "%SCRIPT_DIR%config.json" (
        for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Content '%SCRIPT_DIR%config.json' | ConvertFrom-Json).pass" 2^>nul') do set "POSTGRESQL_PASS=%%I"
    )

    :: POSTGRESQL (Adattamento per Windows)
    echo Verifico e configuro PostgreSQL...
    
    if defined POSTGRESQL_PASS (
        if not "!POSTGRESQL_PASS!"=="null" (
            if not "!POSTGRESQL_PASS!"=="" (
                psql -U postgres -c "ALTER USER postgres WITH PASSWORD '!POSTGRESQL_PASS!';"
            )
        )
    )

    :: Creazione database
    psql -U postgres -c "CREATE DATABASE evolution;" >nul 2>&1
    psql -U postgres -c "CREATE DATABASE images;" >nul 2>&1

    :: Configurazione ambiente virtuale Python e dipendenze
    python -m venv "%SCRIPT_DIR%.venv"
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    python -m pip install -r "%SCRIPT_DIR%requirements.txt"

    type nul > "%SCRIPT_DIR%%FLAG_FILE%"
    echo Installazione completata con successo
)