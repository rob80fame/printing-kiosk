#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure jq is available
if ! command -v jq >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y jq
fi

# Nome del file di controllo
POSTGRESQL_PASS=$(jq -r '.pass' "$SCRIPT_DIR/config.json")
API_KEY=$(jq -r '.apikey' "$SCRIPT_DIR/config.json")
FLAG_FILE="isInstalled"

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
if [ -f "$SCRIPT_DIR/$FLAG_FILE" ]; then
    echo "Il file '$FLAG_FILE' è presente. Avvio del programma..."

    if command -v pm2 >/dev/null 2>&1; then
        pm2 start "$SCRIPT_DIR/backend.py" --interpreter python3 --name KioskBackend || true
        pm2 start "$SCRIPT_DIR/app.py" --interpreter python3 --name KioskFrontend || true
    else
        python3 "$SCRIPT_DIR/backend.py" &
        python3 "$SCRIPT_DIR/app.py" &
    fi

else
    echo "Il file '$FLAG_FILE' non esiste. Avvio procedura di installazione..."

    sudo apt-get update -y
    sudo apt-get upgrade -y

    # POSTGRESQL
    sudo apt-get install -y postgresql postgresql-contrib
    sudo service postgresql start
    if [ -n "$POSTGRESQL_PASS" ] && [ "$POSTGRESQL_PASS" != "null" ]; then
        sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '$POSTGRESQL_PASS';"
    fi
    sudo -u postgres createdb evolution || true
    sudo -u postgres createdb images || true

    # REDIS
    sudo apt-get install -y redis-server
    sudo service redis-server start
    redis-cli ping || true

    # NVM / Node
    sudo apt-get install -y curl
    if [ ! -d "$HOME/.nvm" ]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    fi
    if [ -s "$HOME/.nvm/nvm.sh" ]; then
        # shellcheck disable=SC1090
        . "$HOME/.nvm/nvm.sh"
    fi
    nvm install v20.10.0
    nvm use v20.10.0

    # EVOLUTION API
    if [ ! -d "$SCRIPT_DIR/evolution-api" ]; then
        git clone -b v2.0.0 https://github.com/evolution-foundation/evolution-api.git "$SCRIPT_DIR/evolution-api"
    fi
    cd "$SCRIPT_DIR/evolution-api"
    npm install || true
    # Modify .env.example and copy to .env
    if [ -f ".env.example" ]; then
        sed -i "s|YOUR_CUSTOM_API_KEY|$API_KEY|g" .env.example || true
        sed -i "s|PASS|$POSTGRESQL_PASS|g" .env.example || true
        cp .env.example .env
    fi

    chmod +x local_install.sh || true
    ./local_install.sh || true

    npm install -g pm2 || true
    sudo env PATH="$PATH" pm2 startup systemd -u "$USER" --hp "$HOME" || true

    pm2 start npm --name ApiEvolution --prefix "$SCRIPT_DIR/evolution-api" -- run start:prod || true
    pm2 start "$SCRIPT_DIR/backend.py" --interpreter python3 --name KioskBackend || true
    pm2 start "$SCRIPT_DIR/app.py" --interpreter python3 --name KioskFrontend || true
    pm2 save --force || true

    # Wait for API to be ready
    until curl --silent --head --fail http://localhost:8080 >/dev/null 2>&1; do
        sleep 1
    done
    echo "API pronta! Apro il browser per la configurazione..."
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8080/manager" || true
    fi

    if ! command -v libreoffice &> /dev/null; then
        echo "LibreOffice non trovato, procedo con l'installazione..."
        sudo apt-get install -y libreoffice
    else
        echo "LibreOffice è già installato."
    fi

    if ! command -v lp &> /dev/null; then
        echo "Il sistema di stampa non è presente. Installazione di cups-client..."
        sudo apt-get install -y cups-client
    else
        echo "Il comando 'lp' è già disponibile."
    fi

    # PYTHON + venv
    sudo apt-get install -y python3 python3-venv python3-pip
    python3 -m venv "$SCRIPT_DIR/.venv"
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/.venv/bin/activate"
    python -m pip install --upgrade pip
    python -m pip install nicegui psycopg2-binary pymupdf pillow flask requests cryptography || true

    touch "$SCRIPT_DIR/$FLAG_FILE"
    echo "Installazione completata con successo."
fi