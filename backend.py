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
import shutil
import ctypes
from nicegui import ui
import sys
from git import Repo, GitCommandError


app = Flask(__name__)

with open('config.json', 'r') as f:
    file = json.load(f)

Proj_path = os.getcwd()
Doc_path = os.path.join(Proj_path, "DOCUMENTS")
Img_path = os.path.join(Proj_path, "IMAGES")
TMP_DIR = "tmp"
API_URL = "http://localhost:8080"
INSTANCE = file['name']
API_KEY = file['apikey']
db_pass = file['pass']
usb_code = file['usb_code']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

def check_for_git_updates():
    if not os.path.exists('.git'):
        print("Cartella .git non trovata. Controllo aggiornamenti saltato.")
        return

    print("Controllo aggiornamenti via GitPython...")
    try:
        repo = Repo('.')
        
        # Verifica che il repository non sia in uno stato 'dirty' o staccato
        if repo.is_dirty(untracked_files=False):
            print("Attenzione: Ci sono modifiche locali non salvate. Pulled disabilitato.")
            return

        origin = repo.remotes.origin
        
        # Aggiorna le informazioni sui branch remoti
        origin.fetch()

        # Ottiene il branch locale attivo (es. 'main') e il relativo branch remoto di tracciamento
        current_branch = repo.active_branch
        tracking_branch = current_branch.tracking_branch()

        if tracking_branch is None:
            print(f"Nessun branch remoto associato a {current_branch.name}.")
            return

        # Confronta gli hash dei commit
        local_commit = current_branch.commit
        remote_commit = tracking_branch.commit

        if local_commit != remote_commit:
            print(f"Nuovo aggiornamento trovato! ({local_commit.hexsha[:7]} -> {remote_commit.hexsha[:7]})")
            print("Download in corso...")
            
            # Esegue il pull
            origin.pull()
            
            print("Aggiornamento completato con successo. Riavvio dell'applicazione...")
            
            # Riavvia il processo Python per caricare il nuovo codice scaricato
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print("Il software è già aggiornato all'ultima versione.")

    except GitCommandError as e:
        print(f"Errore durante la comunicazione con Git (es. manca connessione): {e}")
    except Exception as e:
        print(f"Errore imprevisto durante il controllo aggiornamenti: {e}")

os.makedirs(TMP_DIR, exist_ok=True)

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

SUPPORTED_EMAIL_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx")

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
                        filename = part.get_filename()
                        if filename and filename.lower().endswith(SUPPORTED_EMAIL_EXTENSIONS):
                            ext = filename.lower()
                            
                            # Struttura condizionale corretta per evitare sovrascrizioni di target_dir
                            if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                target_dir = Img_path
                                is_doc = False
                            elif ext.endswith(('.doc', '.docx')):
                                target_dir = Doc_path
                                is_doc = True
                            else:
                                target_dir = Doc_path
                                is_doc = False

                            Path(target_dir).mkdir(parents=True, exist_ok=True)
                            filepath = os.path.join(target_dir, filename)

                            # 1. Salva prima l'allegato grezzo su disco
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                with open(filepath, "wb") as f:
                                    f.write(payload)
                            elif isinstance(payload, str):
                                with open(filepath, "w", encoding="utf-8") as f:
                                    f.write(payload)

                            # 2. Se è un file Word, converte il file appena salvato in PDF
                            if is_doc:
                                base_name = os.path.splitext(filename)[0]
                                pdf_path = os.path.join(Doc_path, f"{base_name}.pdf")
                                
                                print(f"--- [DOC] Conversione in PDF in corso... ---")
                                try:
                                    convert(filepath, pdf_path)
                                    print(f"--- [DOC] Conversione riuscita: {pdf_path} ---")
                                    final_path = pdf_path 
                                except Exception as conv_err:
                                    print(f"--- [DOC] Errore conversione PDF: {conv_err} ---")
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
import json
import psycopg2

def clear_usb_files_from_db(usb_code):
    """Sovrascrive la colonna file_paths con un array vuoto solo per la specifica entry associata al codice USB."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        empty_files = json.dumps([])
        # Aggiorna solo la riga corrispondente allo specifico usb_code
        cur.execute("UPDATE orders SET file_paths = %s WHERE code = %s;", (empty_files, usb_code))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"--- [USB] Chiavetta rimossa: file svuotati nel database per il codice {usb_code} ---")
    except Exception as e:
        print(f"--- [USB] Errore durante l'aggiornamento del DB alla rimozione: {e} ---")

def usb_monitor_loop():
    print("--- [USB] Monitoraggio chiavette avviato ---")
    seen_drives = set()
    
    # Rileva le unità rimovibili già presenti all'avvio per ignorarle
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in range(65, 91):
            if bitmask & (1 << (letter - 65)):
                drive = chr(letter) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                    seen_drives.add(drive)
    except Exception as e:
        print(f"Errore scansione iniziale USB: {e}")

    while True:
        try:
            current_drives = set()
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in range(65, 91):
                if bitmask & (1 << (letter - 65)):
                    drive = chr(letter) + ":\\"
                    if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                        current_drives.add(drive)
            
            # 1. Rileva inserimento di nuove chiavette
            new_drives = current_drives - seen_drives
            for drive in new_drives:
                print(f"\n--- [USB] Nuova chiavetta rilevata: {drive} ---")
                
                files_found = False
                Path(TMP_DIR).mkdir(parents=True, exist_ok=True)
                
                for root, dirs, files in os.walk(drive):
                    for file in files:
                        if file.lower().endswith(SUPPORTED_EMAIL_EXTENSIONS):
                            src_path = os.path.join(root, file)
                            dst_path = os.path.join(TMP_DIR, file)
                            
                            try:
                                shutil.copy(src_path, dst_path)
                                final_path = dst_path
                                
                                if file.lower().endswith(('.doc', '.docx')):
                                    base_name = os.path.splitext(file)[0]
                                    pdf_path = os.path.join(TMP_DIR, f"{base_name}.pdf")
                                    convert(dst_path, pdf_path)
                                    final_path = pdf_path
                                
                                register_or_append_file(usb_code, final_path)
                                files_found = True
                            except Exception as file_err:
                                print(f"--- [USB] Errore elaborazione file {file}: {file_err} ---")

            # 2. Rileva rimozione di chiavette esistenti
            removed_drives = seen_drives - current_drives
            for drive in removed_drives:
                print(f"\n--- [USB] Chiavetta rimossa: {drive} ---")
                clear_usb_files_from_db(usb_code)

                with open('tmp.json', 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=4)
                print("File tmp.json pulito con successo.")

                folder = TMP_DIR
                if os.path.exists(folder):
                    files = os.listdir(folder)
                    for filename in files:
                        file_path = os.path.join(folder, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                print(f"--- [CLEANUP] Eliminato: {filename} ---")
                        except Exception as e:
                            print(f"--- [CLEANUP] Errore eliminazione {filename}: {e} ---")
                    print(f"--- [CLEANUP] Cartella '{folder}' pulita ---")
                else:
                    print(f"--- [CLEANUP] Cartella '{folder}' non trovata, saltata ---")

            seen_drives = current_drives
            
        except Exception as e:
            print(f"--- [USB] Errore nel ciclo di monitoraggio: {e} ---")
        
        time.sleep(2)

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

def admin_app():
    @ui.page('/')
    def page2():
        ui.label("Pannello Admin - Prezzi in Tempo Reale").classes('text-2xl font-bold mb-4')
        
        container = ui.column().classes('w-full gap-2')
        
        def update_data():
            container.clear()
            file_path = 'tmp.json'
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    with container:
                        if not data:
                            ui.label("Il file tmp.json è vuoto.").classes('text-gray-500')
                        else:
                            with ui.table(
                                columns=[
                                    {'name': 'key', 'label': 'Codice', 'field': 'key', 'align': 'left'},
                                    {'name': 'value', 'label': 'Valore / Prezzo', 'field': 'value', 'align': 'left'},
                                ],
                                rows=[{'key': k, 'value': v} for k, v in data.items()]
                            ).classes('w-full'):
                                pass
                except Exception as e:
                    with container:
                        ui.label(f"Errore di lettura JSON: {e}").classes('text-red-500 text-sm')
            else:
                with container:
                    ui.label("In attesa del file tmp.json...").classes('text-gray-400 italic')

        # Aggiornamento iniziale e polling tramite timer ogni 2 secondi
        update_data()
        ui.timer(2.0, update_data)

    ui.run(port=7776, host='0.0.0.0', reload=False, show=False)

if __name__ == '__main__':
    
    check_for_git_updates()

    init_db()

    # Avvia il monitoraggio USB in background
    usb_thread = threading.Thread(target=usb_monitor_loop, daemon=True)
    usb_thread.start()

    # Avvia il monitoraggio email in background
    monitor_thread = threading.Thread(
        target=email_monitor_loop, args=(30,), daemon=True
    )
    monitor_thread.start()

    t = threading.Thread(target=admin_app, daemon=True)
    t.start()

    app.run(port=8080, debug=False)

    

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n--- [BACKGROUND] Arresto dei servizi in corso... ---")

    