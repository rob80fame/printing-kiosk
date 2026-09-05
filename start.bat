@echo off
setlocal enabledelayedexpansion

:: Resolve script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Leggi le credenziali da config.json tramite PowerShell
if exist "%SCRIPT_DIR%config.json" (
    for /f "tokens=*" %%i in ('powershell -Command "(Get-Content '%SCRIPT_DIR%config.json' | ConvertFrom-Json).pass"') do set "POSTGRESQL_PASS=%%i"
    for /f "tokens=*" %%i in ('powershell -Command "(Get-Content '%SCRIPT_DIR%config.json' | ConvertFrom-Json).apikey"') do set "API_KEY=%%i"
) else (
    set "POSTGRESQL_PASS="
    set "API_KEY="
)

set "FLAG_FILE=isInstalled"

:: Controlla se è un repository Git valido
if exist "%SCRIPT_DIR%.git" (
    echo Controllo aggiornamenti via Git...
    git fetch origin main -q
    
    for /f "tokens=*" %%i in ('git rev-parse HEAD') do set "LOCAL=%%i"
    for /f "tokens=*" %%i in ('git rev-parse origin/main') do set "REMOTE=%%i"
    
    if not "!LOCAL!"=="!REMOTE!" (
        echo Trovato un aggiornamento su GitHub! Applicazione in corso...
        git pull origin main
        echo Aggiornamento completato con successo.
    ) else (
        echo Il software è già aggiornato all'ultima versione.
    )
)

:: Controllo se il file flag esiste
if exist "%SCRIPT_DIR%%FLAG_FILE%" (
    echo Il file '%FLAG_FILE%' è presente. Avvio del programma...
    
    if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
        start "" "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%backend.py"
        "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%app.py"
    ) else (
        start "" python "%SCRIPT_DIR%backend.py"
        python "%SCRIPT_DIR%app.py"
    )
) else (
    echo Il file '%FLAG_FILE%' non esiste. Avvio procedura di installazione...

    :: Installazione o verifica PostgreSQL tramite winget
    winget install --id PostgreSQL.PostgreSQL -e --silent --accept-package-agreements --accept-source-agreements || echo PostgreSQL potrebbe essere già installato.

    :: Clona evolution-api se non presente
    if not exist "%SCRIPT_DIR%evolution-api" (
        git clone https://github.com/evolution-foundation/evolution-api.git "%SCRIPT_DIR%evolution-api"
    )

    cd /d "%SCRIPT_DIR%evolution-api"

    :: Creazione file .env
    (
        echo SERVER_NAME=evolution
        echo SERVER_TYPE=http
        echo SERVER_PORT=8080
        echo SERVER_URL=http://localhost:8080
        echo EVENT_EMITTER_MAX_LISTENERS=50
        echo DEL_INSTANCE=false
        echo AUTHENTICATION_API_KEY=!API_KEY!
        echo DATABASE_PROVIDER=postgresql
        echo DATABASE_CONNECTION_URI=postgresql://postgres:!POSTGRESQL_PASS!@localhost:5432/evolution?schema=public
        echo DATABASE_SAVE_DATA_INSTANCE=false
        echo DATABASE_SAVE_DATA_NEW_MESSAGE=true
        echo DATABASE_SAVE_MESSAGE_UPDATE=false
        echo DATABASE_SAVE_DATA_CONTACTS=false
        echo DATABASE_SAVE_DATA_CHATS=true
        echo DATABASE_SAVE_DATA_LABELS=false
        echo DATABASE_SAVE_DATA_HISTORIC=false
        echo DATABASE_SAVE_IS_ON_WHATSAPP=false
        echo DATABASE_SAVE_IS_ON_WHATSAPP_DAYS=false
        echo DATABASE_DELETE_MESSAGE=true
        echo WEBHOOK_GLOBAL_ENABLED=true
        echo WEBHOOK_GLOBAL_URL=http://127.0.0.1:8080/webhook
        echo WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false
        echo WEBHOOK_EVENTS_APPLICATION_STARTUP=false
        echo WEBHOOK_EVENTS_QRCODE_UPDATED=false
        echo WEBHOOK_EVENTS_MESSAGES_SET=false
        echo WEBHOOK_EVENTS_MESSAGES_UPSERT=true
        echo WEBHOOK_EVENTS_MESSAGES_EDITED=false
        echo WEBHOOK_EVENTS_MESSAGES_UPDATE=false
        echo WEBHOOK_EVENTS_MESSAGES_DELETE=false
        echo WEBHOOK_EVENTS_SEND_MESSAGE=true
        echo WEBHOOK_EVENTS_SEND_MESSAGE_UPDATE=false
        echo WEBHOOK_EVENTS_CONTACTS_SET=false
        echo WEBHOOK_EVENTS_CONTACTS_UPSERT=false
        echo WEBHOOK_EVENTS_CONTACTS_UPDATE=false
        echo WEBHOOK_EVENTS_PRESENCE_UPDATE=false
        echo WEBHOOK_EVENTS_CHATS_SET=false
        echo WEBHOOK_EVENTS_CHATS_UPSERT=false
        echo WEBHOOK_EVENTS_CHATS_UPDATE=false
        echo WEBHOOK_EVENTS_CHATS_DELETE=false
        echo WEBHOOK_EVENTS_GROUPS_UPSERT=false
        echo WEBHOOK_EVENTS_GROUPS_UPDATE=false
        echo WEBHOOK_EVENTS_GROUP_PARTICIPANTS_UPDATE=false
        echo WEBHOOK_EVENTS_CONNECTION_UPDATE=false
        echo WEBHOOK_EVENTS_REMOVE_INSTANCE=false
        echo WEBHOOK_EVENTS_LOGOUT_INSTANCE=false
        echo WEBHOOK_EVENTS_LABELS_EDIT=false
        echo WEBHOOK_EVENTS_LABELS_ASSOCIATION=false
        echo WEBHOOK_EVENTS_CALL=false
        echo WEBHOOK_EVENTS_ERRORS=false
        echo CONFIG_SESSION_PHONE_CLIENT=PrintingKiosk
        echo CONFIG_SESSION_PHONE_NAME=Chrome
        echo QRCODE_LIMIT=30
        echo QRCODE_COLOR=#175197
        echo CACHE_REDIS_ENABLED=false
        echo CACHE_LOCAL_ENABLED=true
        echo AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
        echo LANGUAGE=en
    ) > ".env"

    cd /d "%SCRIPT_DIR%"

    :: Gestione dei processi con PM2 per Windows
    call npm install -g pm2 || true
    call pm2 start npm --name ApiEvolution --prefix "%SCRIPT_DIR%evolution-api" -- run start:prod || true
    call pm2 start "%SCRIPT_DIR%backend.py" --interpreter python --name KioskBackend || true
    call pm2 start "%SCRIPT_DIR%app.py" --interpreter python --name KioskFrontend || true
    call pm2 save --force || true

    :: Attesa che l'API sia pronta
    :WaitLoop
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8080' -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
    if errorlevel 1 (
        timeout /t 1 /nobreak > nul
        goto WaitLoop
    )

    echo API pronta! Apro il browser per la configurazione...
    start http://localhost:8080/manager

    :: Controllo e installazione LibreOffice
    where soffice >nul 2>&1
    if %errorlevel% neq 0 (
        echo LibreOffice non trovato, procedo con l'installazione...
        winget install --id TheDocumentFoundation.LibreOffice -e --silent --accept-package-agreements --accept-source-agreements || true
    ) else (
        echo LibreOffice è già installato.
    )

    :: Configurazione ambiente virtuale Python e dipendenze
    python -m venv "%SCRIPT_DIR%.venv"
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    python -m pip install nicegui psycopg2-binary pymupdf pillow flask requests cryptography || true

    echo. > "%SCRIPT_DIR%%FLAG_FILE%"
    echo Installazione completata con successo.
)