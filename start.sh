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

        python3 "$SCRIPT_DIR/backend.py" &
        python3 "$SCRIPT_DIR/app.py"

else
    echo "Il file '$FLAG_FILE' non esiste. Avvio procedura di installazione..."

    sudo apt-get update -y
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
    git clone https://github.com/evolution-foundation/evolution-api.git "$SCRIPT_DIR/evolution-api"

    cd "$SCRIPT_DIR/evolution-api"

    cat << EOF > ".env"
        SERVER_NAME=evolution
        SERVER_TYPE=http
        SERVER_PORT=8080
        SERVER_URL=http://localhost:8080
        EVENT_EMITTER_MAX_LISTENERS=50
        DEL_INSTANCE=false
        AUTHENTICATION_API_KEY= $API_KEY
        DATABASE_PROVIDER=postgresql
        DATABASE_CONNECTION_URI=postgresql://postgres:$POSTGRESQL_PASS@localhost:5432/evolution?schema=public

        DATABASE_SAVE_DATA_INSTANCE=false
        DATABASE_SAVE_DATA_NEW_MESSAGE=true
        DATABASE_SAVE_MESSAGE_UPDATE=false
        DATABASE_SAVE_DATA_CONTACTS=false
        DATABASE_SAVE_DATA_CHATS=true
        DATABASE_SAVE_DATA_LABELS=false
        DATABASE_SAVE_DATA_HISTORIC=false
        DATABASE_SAVE_IS_ON_WHATSAPP=false
        DATABASE_SAVE_IS_ON_WHATSAPP_DAYS=false
        DATABASE_DELETE_MESSAGE=true

        WEBHOOK_GLOBAL_ENABLED=true
        WEBHOOK_GLOBAL_URL='http://127.0.0.1:8080/webhook'
        WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false
        WEBHOOK_EVENTS_APPLICATION_STARTUP=false
        WEBHOOK_EVENTS_QRCODE_UPDATED=false
        WEBHOOK_EVENTS_MESSAGES_SET=false
        WEBHOOK_EVENTS_MESSAGES_UPSERT=true
        WEBHOOK_EVENTS_MESSAGES_EDITED=false
        WEBHOOK_EVENTS_MESSAGES_UPDATE=false
        WEBHOOK_EVENTS_MESSAGES_DELETE=false
        WEBHOOK_EVENTS_SEND_MESSAGE=true
        WEBHOOK_EVENTS_SEND_MESSAGE_UPDATE=false
        WEBHOOK_EVENTS_CONTACTS_SET=false
        WEBHOOK_EVENTS_CONTACTS_UPSERT=false
        WEBHOOK_EVENTS_CONTACTS_UPDATE=false
        WEBHOOK_EVENTS_PRESENCE_UPDATE=false
        WEBHOOK_EVENTS_CHATS_SET=false
        WEBHOOK_EVENTS_CHATS_UPSERT=false
        WEBHOOK_EVENTS_CHATS_UPDATE=false
        WEBHOOK_EVENTS_CHATS_DELETE=false
        WEBHOOK_EVENTS_GROUPS_UPSERT=false
        WEBHOOK_EVENTS_GROUPS_UPDATE=false
        WEBHOOK_EVENTS_GROUP_PARTICIPANTS_UPDATE=false
        WEBHOOK_EVENTS_CONNECTION_UPDATE=false
        WEBHOOK_EVENTS_REMOVE_INSTANCE=false
        WEBHOOK_EVENTS_LOGOUT_INSTANCE=false
        WEBHOOK_EVENTS_LABELS_EDIT=false
        WEBHOOK_EVENTS_LABELS_ASSOCIATION=false
        WEBHOOK_EVENTS_CALL=false
        WEBHOOK_EVENTS_ERRORS=false

        CONFIG_SESSION_PHONE_CLIENT=PrintingKiosk
        CONFIG_SESSION_PHONE_NAME=Chrome

        QRCODE_LIMIT=30
        QRCODE_COLOR='#175197'

        CACHE_REDIS_ENABLED=true
        CACHE_REDIS_URI=redis://localhost:6379
        CACHE_REDIS_TTL=604800
        CACHE_REDIS_PREFIX_KEY=evolution
        CACHE_REDIS_SAVE_INSTANCES=false
        CACHE_LOCAL_ENABLED=false

        AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
        LANGUAGE=en

        EOF

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
        firefox --new-tab "http://localhost:8080/manager"
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