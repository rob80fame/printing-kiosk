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
import email
import imaplib
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
import threading
import time
from pathlib import Path
import xml.etree.ElementTree as ET


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

def get_servers_from_email(email_address):
    """Ricava i server IMAP e SMTP interrogando il database di autoconfigurazione di Thunderbird."""
    domain = email_address.split("@")[-1].lower()
    
    # Mappa rapida per i provider più comuni (evita la richiesta HTTP se non necessaria)
    known_providers = {
        "gmail.com": {"imap": "imap.gmail.com", "smtp": "smtp.gmail.com", "port": 587},
        "outlook.com": {"imap": "outlook.office365.com", "smtp": "outlook.office365.com", "port": 587},
        "hotmail.com": {"imap": "outlook.office365.com", "smtp": "outlook.office365.com", "port": 587},
        "yahoo.com": {"imap": "imap.mail.yahoo.com", "smtp": "imap.mail.yahoo.com", "port": 587},
        "icloud.com": {"imap": "imap.mail.me.com", "smtp": "imap.mail.me.com", "port": 587},
        "aruba.it": {"imap": "imap.aruba.it", "smtp": "smtp.aruba.it", "port": 587},
        "libero.it": {"imap": "imap.libero.it", "smtp": "smtp.libero.it", "port": 587}
    }
    
    if domain in known_providers:
        return known_providers[domain]

    # Interrogazione del database pubblico Mozilla Thunderbird Autoconfig
    url = f"https://autoconfig.thunderbird.net/v1.1/{domain}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            imap_node = root.find(".//incomingServer[@type='imap']/hostname")
            smtp_node = root.find(".//outgoingServer[@type='smtp']/hostname")
            
            imap_server = imap_node.text if imap_node is not None else f"imap.{domain}"
            smtp_server = smtp_node.text if smtp_node is not None else f"smtp.{domain}"
            
            return {"imap": imap_server, "smtp": smtp_server, "port": 587}
    except Exception:
        pass
        
    # Fallback standard basato sul nome del dominio se Thunderbird fallisce
    return {
        "imap": f"imap.{domain}",
        "smtp": f"smtp.{domain}",
        "port": 587
    }

EMAIL_USER = file['EMAIL_USER']
EMAIL_PASS = file['EMAIL_PASS']
if EMAIL_USER:
    servers = get_servers_from_email(EMAIL_USER)
    IMAP_SERVER = servers["imap"]
    SMTP_SERVER = servers["smtp"]
    SMTP_PORT = 587

SUPPORTED_EMAIL_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".webp")

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
                    final_path = pdf_path 
                except Exception as conv_err:
                    print(f"--- [DOC] Errore conversione PDF: {conv_err} ---")
            
            code = register_or_append_file(mittente, final_path)
            invia_risposta(mittente, f"Documento ricevuto! Il tuo codice per la stampa è: {code}")
            
        else:
            print(f"--- [DOC] Errore download. Status: {resp.status_code} ---")
            
    except Exception as e:
        print(f"--- [DOC] ERRORE CRITICO: {e} ---")

def convert(file_path, output_dir):
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
    if file.get('mode', 'send') == "send":
        url = f"{API_URL}/message/sendText/{INSTANCE}"
        headers = {"apikey": API_KEY, "Content-Type": "application/json"}
        requests.post(url, json={"number": destinatario, "text": testo}, headers=headers)
        print(f"--- [TESTO] Risposta inviata ---")
    else:
        print (f'Volevo mandare a {destinatario} il messaggio {testo} ma mi hai zittito')

def send_email_reply(recipient_email, code):
    """Invia risposta via email al mittente con il codice di stampa."""
    if not recipient_email or not EMAIL_USER:
        return
    try:
        msg = EmailMessage()
        msg.set_content(f"File ricevuto! Il tuo codice per la stampa è: {code}")
        msg['Subject'] = "Conferma ricezione e codice stampa - Kiosk"
        msg['From'] = EMAIL_USER
        msg['To'] = recipient_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"[EMAIL] Risposta inviata con successo a {recipient_email} (Codice: {code})")
    except Exception as e:
        print(f"[EMAIL] Errore invio risposta SMTP: {e}")

def process_incoming_emails():
    if not EMAIL_USER or not EMAIL_PASS:
        return
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            mail.logout()
            return

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return

        msg_list = messages[0].split()
        if not msg_list:
            mail.logout()
            return

        for num in msg_list:
            status, data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    raw_from = msg.get("From", "")
                    _, sender_email = parseaddr(raw_from)

                    file_saved = False
                    saved_file_path = None

                    for part in msg.walk():
                        if part.get_content_maintype() == "multipart":
                            continue
                        if part.get("Content-Disposition") is None:
                            continue

                        filename = part.get_filename()
                        if filename and filename.lower().endswith(SUPPORTED_EMAIL_EXTENSIONS):
                            # Se è immagine va in IMAGES, se è PDF va in DOCUMENTS
                            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                target_dir = Img_path
                            else:
                                target_dir = Doc_path

                            Path(target_dir).mkdir(parents=True, exist_ok=True)
                            filepath = os.path.join(target_dir, filename)

                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                with open(filepath, "wb") as f:
                                    f.write(payload)
                                print(f"[EMAIL] File allegato salvato: {filename}")
                                file_saved = True
                                saved_file_path = filepath

                    if file_saved and sender_email and saved_file_path:
                        code = register_or_append_file(sender_email, saved_file_path)
                        send_email_reply(sender_email, code)

            mail.store(num, "+FLAGS", "\\Seen")

        mail.logout()
    except Exception as e:
        print(f"[EMAIL] Errore nel ciclo IMAP: {e}")

def email_monitor_loop(interval_seconds=30):
    print(f"Servizio ricezione email IMAP avviato (controllo ogni {interval_seconds}s)...")
    while True:
        process_incoming_emails()
        time.sleep(interval_seconds)

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
    init_db()
    
    # Avvia il monitoraggio email in background
    monitor_thread = threading.Thread(
        target=email_monitor_loop, args=(30,), daemon=True
    )
    monitor_thread.start()

    app.run(port=8080, debug=False)