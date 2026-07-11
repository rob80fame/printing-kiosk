import os
import json

with open('config.json', 'r') as f:
    file = json.load(f)

mode = file['mode']

db_pass = file['pass']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

npm_dir = file['npmdir']

instance_name = file['name']

phonenum = file['phonenum']

remoteJidAlt = f"{phonenum}@s.whatsapp.net"

apikey = file['apikey']

Proj_path = os.getcwd()

Doc_path = os.path.join(Proj_path, "DOCUMENTS")

Img_path = os.path.join(Proj_path, "IMAGES")

PRINTER = file['Printer']

sudo = file['sudo']

shutp = file['shutp']

in_t = file['inactivity_t']

Tmpjson = 'tmp.json'

def registertmpprice(user_id, amount_str):
    new_price = float(amount_str.replace('€', '').replace(',', '.').strip())
    
    if os.path.exists(Tmpjson):
        with open(Tmpjson, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    # 3. Calcola il nuovo totale
    if user_id in data:
        current_price_str = data[user_id].replace('€', '').replace(',', '.').strip()
        current_price = float(current_price_str)
        total = current_price + new_price
    else:
        total = new_price
    
    data[user_id] = f"€ {total:.2f}".replace('.', ',')
    
    with open(Tmpjson, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def readtmpprice(user_id):
    if not os.path.exists(Tmpjson):
        return "€ 0,00"
        
    with open(Tmpjson, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data.get(str(user_id), "€ 0,00")
        except (json.JSONDecodeError, KeyError):
            return "€ 0,00"
    