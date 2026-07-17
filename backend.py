from flask import Flask, request
import os
import requests
import mimetypes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import base64
import psycopg2
import json
import random
import subprocess
import platform


app = Flask(__name__)

with open('config.json', 'r') as f:
    file = json.load(f)

Proj_path = os.getcwd()
Doc_path = os.path.join(Proj_path, "DOCUMENTS")
Img_path = os.path.join(Proj_path, "IMAGES")
API_URL = "http://localhost:8080"
INSTANCE = file['name']
API_KEY = file['apikey']
db_pass = file['pass']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

if not os.path.exists(Doc_path): 
    os.makedirs(Doc_path)
if not os.path.exists(Img_path): 
    os.makedirs(Img_path)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    if not payload or payload.get('event') != 'messages.upsert':
        return "OK", 200

    data = payload.get('data', {})
    msg_type = data.get('messageType')

    if msg_type == 'conversation':
        process_text(data)
        
    if msg_type == 'imageMessage':
        process_media(data)

    elif msg_type == 'documentMessage':
        process_document(data)

    return "OK", 200

def process_media(data):
    
    mittente = data.get('key', {}).get('remoteJid')
    msg_content = data.get('message', {})
    image_data = msg_content.get('imageMessage', {})
    
    if not image_data or 'url' not in image_data or 'mediaKey' not in image_data:
        return

    media_key = image_data.get('mediaKey')
    msg_id = data.get('key', {}).get('id')
    mimetype = image_data.get('mimetype')
    
    ext = mimetypes.guess_extension(mimetype) or ".jpg"
    if ext == ".jpe": ext = ".jpeg"

    print(f"--- [MEDIA] Download in corso: img_{msg_id}{ext} ---")
    
    try:
        resp = requests.get(image_data.get('url'), timeout=10)
        
        if resp.status_code == 200:
            raw_data = resp.content
            
            decrypted = decrypt_whatsapp_media(raw_data, media_key, "Image")
            
            file_name = f"img_{msg_id}{ext}"
            file_path = os.path.join(Img_path, file_name)
            
            with open(file_path, "wb") as f:
                f.write(decrypted)
            print(f"--- [MEDIA] Immagine salvata con successo: {file_path} ---")
            code = register_or_append_file(mittente, file_path)
            invia_risposta(mittente, f"Immagine ricevuta! Il tuo codice per la stampa è: {code}")
        else:
            print(f"--- [MEDIA] Errore download. Status code: {resp.status_code} ---")
            
    except Exception as e:
        print(f"--- [MEDIA] ERRORE CRITICO: {e} ---")

def process_document(data):
    
    mittente = data.get('key', {}).get('remoteJid')
    msg_content = data.get('message', {})
    doc_data = msg_content.get('documentMessage', {})
    
    if not doc_data or 'url' not in doc_data or 'mediaKey' not in doc_data:
        return

    media_key = doc_data.get('mediaKey')
    msg_id = data.get('key', {}).get('id')

    file_name = doc_data.get('fileName', f"doc_{msg_id}.docx")
    
    file_path = os.path.join(Doc_path, file_name)

    print(f"--- [DOC] Download in corso: {file_name} ---")
    
    try:
        resp = requests.get(doc_data.get('url'), timeout=10)
        
        if resp.status_code == 200:
            raw_data = resp.content
            decrypted = decrypt_whatsapp_media(raw_data, media_key, "Document")
            
            with open(file_path, "wb") as f:
                f.write(decrypted)
            
            print(f"--- [DOC] Documento salvato: {file_path} ---")

            final_path = file_path
            
            if file_name.lower().endswith(('.doc', '.docx')):
                base_name = os.path.splitext(file_name)[0]
                pdf_path = os.path.join(Doc_path, f"{base_name}.pdf")
                
                print(f"--- [DOC] Conversione in PDF in corso... ---")
                try:
                    convert(file_path, pdf_path)
                    print(f"--- [DOC] Conversione riuscita: {pdf_path} ---")
                    final_path = pdf_path # Aggiorniamo il path al PDF
                except Exception as conv_err:
                    print(f"--- [DOC] Errore conversione PDF: {conv_err} ---")
            
            code = register_or_append_file(mittente, final_path)
            invia_risposta(mittente, f"Documento ricevuto! Il tuo codice per la stampa è: {code}")
            
        else:
            print(f"--- [DOC] Errore download. Status: {resp.status_code} ---")
            
    except Exception as e:
        print(f"--- [DOC] ERRORE CRITICO: {e} ---")

def convert(file_path, output_dir):
    ##if Microsoft Word is installed it uses it, else it uses libreoffice
    try:
        if platform.system() == "Windows":
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Quit()
            from docx2pdf import convert as wordconvert
            return wordconvert(file_path, output_dir)
    except Exception:
        subprocess.run(
            f'/opt/libreoffice7.3/program/soffice \
            --headless \
            --convert-to pdf \
            --outdir {output_dir} {file_path}', shell=True)
        
        pdf_file_path = f'{output_dir}{file_path.rsplit("/", 1)[1].split(".")[0]}.pdf'
        
        if os.path.exists(pdf_file_path):
            return pdf_file_path
        else:
            return None

def process_text(data):
    msg_content = data.get('message', {}).get('conversation', "").strip().lower()
    mittente = data.get('key', {}).get('remoteJid')
    
    print(f"--- [TESTO] Ricevuto: {msg_content} ---")

def invia_risposta(destinatario, testo):
    if file['mode'] == "send":
        url = f"{API_URL}/message/sendText/{INSTANCE}"
        headers = {"apikey": API_KEY, "Content-Type": "application/json"}
        requests.post(url, json={"number": destinatario, "text": testo}, headers=headers)
        print(f"--- [TESTO] Risposta inviata ---")
    else:
        print (f'Volevo mandare a {destinatario} il messaggio {testo} ma mi hai zittito')

def decrypt_whatsapp_media(enc_data, media_key_input, media_type):

    if isinstance(media_key_input, dict):
        media_key = bytes([media_key_input[str(i)] for i in range(len(media_key_input))])
    else:
        try:
            media_key = base64.b64decode(media_key_input)
        except:
            media_key = media_key_input
    
    app_info = f"WhatsApp {media_type} Keys"
    hkdf = HKDF(algorithm=hashes.SHA256(), length=112, salt=None, info=app_info.encode('utf-8'), backend=default_backend())
    expanded = hkdf.derive(media_key)
    iv, cipher_key = expanded[0:16], expanded[16:48]

    encrypted_data_clean = enc_data[:-10]
    
    cipher = Cipher(algorithms.AES(cipher_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    data = decryptor.update(encrypted_data_clean) + decryptor.finalize()
    
    try:
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(data) + unpadder.finalize()
    except: 
        pass 
    
    return data

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    query = '''CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                code VARCHAR(10),
                price VARCHAR(10),
                file_paths JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );'''
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()

def register_or_append_file(sender, file_path):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, code FROM orders WHERE sender = %s ORDER BY id DESC LIMIT 1", (sender,))
    row = cur.fetchone()
    
    code = None
    
    if row:
        order_id = row[0]
        code = row[1]
        
        cur.execute("""
            UPDATE orders 
            SET file_paths = file_paths || %s::jsonb
            WHERE id = %s
        """, (json.dumps([file_path]), order_id))
        
        print(f"--- [DB] File aggiunto all'ordine esistente {order_id} ---")
        
    else:
        code = str(random.randint(1000, 9999))
        
        cur.execute("""
            INSERT INTO orders (sender, code, file_paths) 
            VALUES (%s, %s, %s)
        """, (sender, code, json.dumps([file_path])))
        
        print(f"--- [DB] Nuova entry creata con codice {code} ---")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return code

if __name__ == '__main__':
    app.run(port=8080, debug=False)