@echo off
:: Imposta il titolo della finestra principale
title Gestore Avvio Servizi

:: 1. Avvia app.py in una nuova finestra
start "App Python" cmd /k "python app.py"

:: 2. Avvia backend.py in una nuova finestra
start "Backend Python" cmd /k "python backend.py"

:: 3. Entra nella cartella evolution-api ed esegue npm run
start "Evolution API" cmd /k "cd evolution-api && npm start"

:: 4. Attende 3 secondi per consentire ai server di avviarsi
timeout /t 25 /nobreak > nul

:: 5. Apre la pagina nel browser predefinito
start http://localhost:8080/manager/

:: Chiude la finestra di lancio principale, lasciando aperte le sotto-finestre
exit