import os
import json

with open('config.json', 'r') as f:
    file = json.load(f)

#Password set during postgresql configuration
db_pass = file['pass']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

npm_dir = file['npmdir']

#Name of the istance on evolution-api
instance_name = file['name']

phonenum = file['phonenum']
#Phonenumber 
remoteJidAlt = f"{phonenum}@s.whatsapp.net"

#Api key set in .env
apikey = file['apikey']

#Path to project
Proj_path = os.getcwd()

#Docpath
Doc_path = os.path.join(Proj_path, "DOCUMENTS")
#Imgpath
Img_path = os.path.join(Proj_path, "IMAGES")

#Printer name
PRINTER = file['Printer']

##ADMIN PASS
sudo = file['sudo']

FILE_PATH = 'tmp.json'

def registertmpprice(user_id, amount_str):
    # 1. Pulisci la stringa e converti in float
    # Rimuoviamo € e sostituiamo la virgola con il punto per il calcolo
    new_price = float(amount_str.replace('€', '').replace(',', '.').strip())
    
    # 2. Carica i dati (se il file non esiste, crea un dizionario vuoto)
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    # 3. Calcola il nuovo totale
    if user_id in data:
        # Prendi il prezzo attuale, pulisci formato (es: € 0,20 -> 0.20)
        current_price_str = data[user_id].replace('€', '').replace(',', '.').strip()
        current_price = float(current_price_str)
        total = current_price + new_price
    else:
        total = new_price
    
    # 4. Aggiorna il dizionario (formato italiano con virgola)
    data[user_id] = f"€ {total:.2f}".replace('.', ',')
    
    # 5. Salva il file
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def readtmpprice(user_id):
    if not os.path.exists(FILE_PATH):
        return "€ 0,00"
        
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            # Restituisce il valore o "€ 0,00" se l'utente non esiste
            return data.get(str(user_id), "€ 0,00")
        except (json.JSONDecodeError, KeyError):
            return "€ 0,00"
    