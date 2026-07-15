@echo off
:: Script di Setup Kiosk (Evolution API + Backend)
:: ESEGUIRE COME AMMINISTRATORE

echo --- Inizio Setup Kiosk ---
echo.

winget install --id Git.Git -e --source winget
git clone https://github.com/rob80fame/printing-kiosk.git
cd printing-kiosk


:: 1. Installazione Software Base via Winget
echo [1/3] Installazione dipendenze di sistema...
winget install --id OpenJS.NodeJS.LTS -e --source winget
winget install --id PostgreSQL.PostgreSQL -e --source winget
winget install --id Redis.Redis -e --source winget
winget install --id Python.Python.3.12 -e --source winget
winget install --id SumatraPDF.SumatraPDF -e --source winget
winget install --id Git.Git -e --source winget

echo.
echo [IMPORTANTE] Assicurarsi che MS Office 2019 sia installato.
echo Premere un tasto per procedere...
pause

:: 2. Setup Evolution API
echo.
echo [2/3] Setup Evolution API...
if not exist "evolution-api" (
    git clone https://github.com/evolution-foundation/evolution-api.git
)
cd evolution-api
git checkout tags/2.3.7

echo Installazione dipendenze Node...
call npm install

echo Creazione file .env...
if exist .env.example (
    copy .env.example .env
    echo --- CONFIGURARE IL FILE .ENV ORA ---
    echo Apri evolution-api\.env e imposta le credenziali.
    pause
)

echo Creazione Database evolution...
createdb -U postgres evolution

echo Migrazioni Prisma...
call npx prisma migrate deploy --schema ./prisma/postgresql-schema.prisma
cd ..

:: 3. Setup Backend
echo.
echo [3/3] Setup Backend Python...
echo Installazione librerie Python...
pip install flask psycopg2-binary cryptography requests docx2pdf sv-ttk

echo Creazione Database images...
:: Assicurarsi che il percorso di createdb corrisponda alla versione installata
"C:\Program Files\PostgreSQL\18\bin\createdb.exe" -U postgres images

echo Configurazione file config.json...
if exist "config_example.json" (
    copy config_example.json config.json
    echo --- CONFIGURARE IL FILE config.json ORA ---
    pause
)

:: 4. Task Scheduler (Corretto con il percorso corrente)
echo Configurazione Task Scheduler...
set "CURRENT_DIR=%~dp0"
schtasks /create /tn "kiosk_cleanup" /tr "python '%CURRENT_DIR%cleanup.py'" /sc daily /st 20:00 /f

echo.
echo --- SETUP COMPLETATO ---
echo Avviare l'API con 'npm start' dentro la cartella evolution-api
pause