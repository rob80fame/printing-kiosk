#!/bin/bash

# Nome del file di controllo
FLAG_FILE="installed"
POSTGRESQL_PASS = ""
SCRIPT_DIR="$(dirname "$0")"

# Controllo se il file esiste
if [ -f "$FLAG_FILE" ]; then
    echo "Il file '$FLAG_FILE' è presente. Avvio del programma..."
    
    # Inserisci qui il comando per avviare il tuo programma
    ./tuo_programma_eseguibile
    
else
    echo "Il file '$FLAG_FILE' non esiste. Avvio procedura di installazione..."

    sudo apt-get update -y
    sudo apt-get upgrade -y

    #POSTGRESQL
    sudo apt-get install postgresql postgresql-contrib
    sudo -u postgres psql -c "ALTER USER nome_utente WITH PASSWORD '$POSTGRESQL_PASS';"
    sudo service postgresql start
    sudo -u postgres createdb evolution

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
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/evolution-api/.env"

    npm run db:generate
    npm run db:deploy

    npm run build
    npm run start:prod

    npm install pm2 -g
    pm2 start 'npm run start:prod' --name ApiEvolution
    pm2 startup
    pm2 save --force


    #PYTHON
    sudo apt install python3
    
    pip install flask psycopg2-binary cryptography requests docx2pdf sv-ttk

    touch "$FLAG_FILE"
    echo "Installazione completata con successo."
fi