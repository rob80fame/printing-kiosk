#!/bin/bash
sudo apt install jq
# Nome del file di controllo
POSTGRESQL_PASS=$(jq -r '.pass' config.json)
API_KEY=$(jq -r '.apikey' config.json)
SCRIPT_DIR="$(dirname "$0")"

# Entra nella cartella dello script
cd "$SCRIPT_DIR"

# Controlla se è un repository Git valido
if [ -d ".git" ]; then
    echo "Controllo aggiornamenti via Git..."
    
    # Aggiorna le informazioni dal remote senza applicarle subito
    git fetch origin main -q
    
    # Confronta il commit locale con quello remoto
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)
    
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "Trovato un aggiornamento su GitHub! Applicazione in corso..."
        git pull origin main
        echo "Aggiornamento completato con successo."
    else
        echo "Il software è già aggiornato all'ultima versione."
    fi
fi

# Controllo se il file esiste
if [ -f "installed" ]; then
    echo "Il file '$FLAG_FILE' è presente. Avvio del programma..."

    python3 backend.py &
    python3 app.py &

else
    echo "Il file '$FLAG_FILE' non esiste. Avvio procedura di installazione..."

    sudo apt-get update -y
    sudo apt-get upgrade -y

    #POSTGRESQL
    sudo apt-get install postgresql postgresql-contrib
    sudo -u postgres psql -c "ALTER USER nome_utente WITH PASSWORD '$POSTGRESQL_PASS';"
    sudo service postgresql start
    sudo -u postgres createdb evolution
    sudo -u postgres createdb images

    #REDIS
    sudo apt-get install redis-server
    sudo service redis-server start
    redis-cli ping

    #NVM
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    source ~/.bashrc
    nvm install v20.10.0 && nvm use v20.10.0
    command -v nvm

    #EVOLUTION API
    git clone -b v2.0.0 https://github.com/evolution-foundation/evolution-api.git
    cd evolution-api
    npm install
    ###MODIFY .env.example
    sed -i 's/YOUR_CUSTOM_API_KEY/'$API_KEY'/g' .env.example
    sed -i 's/PASS/'$POSTGRESQL_PASS'/g' .env.example
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/evolution-api/.env"

    npm run db:generate
    npm run db:deploy

    npm run build
    npm run start:prod

    npm install pm2 -g

    pm2 start 'npm run start:prod' --name ApiEvolution
    pm2 startup
    pm2 save --force

    pm2 start 'python3 '$SCRIPT_DIR'/backend.py' --name KioskBackend
    pm2 startup
    pm2 save --force

    pm2 start 'python3 '$SCRIPT_DIR'/app.py' --name KioskFrontend
    pm2 startup
    pm2 save --force

    while ! nc -z localhost 8080; do   
        sleep 1 # Aspetta 1 secondo prima di riprovare
    done
    echo "API pronta! Apro il browser per la configurazione..."
    xdg-open "http://localhost:8080/manager"

    if ! command -v libreoffice &> /dev/null; then
        echo "LibreOffice non trovato, procedo con l'installazione..."
        sudo apt update -qq
        sudo apt install -y libreoffice
    else
        echo "LibreOffice è già installato."
    fi

    if ! command -v lp &> /dev/null; then
        echo "Il sistema di stampa non è presente. Installazione di cups-client..."
        sudo apt update
        sudo apt install -y cups-client
    else
        echo "Il comando 'lp' è già disponibile."
    fi

    #PYTHON
    sudo apt install python3
    
    pip install nicegui psycopg2-binary pymupdf pillow flask requests cryptography

    touch "'$SCRIPT_DIR'/'$FLAG_FILE'"
    echo "Installazione completata con successo."
fi