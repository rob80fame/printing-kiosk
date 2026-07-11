import os
import requests
import mimetypes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import text_logic
import db_manager
from crypto_utils import decrypt_whatsapp_media
import config

DOWNLOAD_FOLDER = config.Img_path

if not os.path.exists(DOWNLOAD_FOLDER): 
    os.makedirs(DOWNLOAD_FOLDER)

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
            file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
            
            with open(file_path, "wb") as f:
                f.write(decrypted)
            print(f"--- [MEDIA] Immagine salvata con successo: {file_path} ---")
            code = db_manager.register_or_append_file(mittente, file_path)
            text_logic.invia_risposta(mittente, f"Immagine ricevuta! Il tuo codice per la stampa è: {code}")
        else:
            print(f"--- [MEDIA] Errore download. Status code: {resp.status_code} ---")
            
    except Exception as e:
        print(f"--- [MEDIA] ERRORE CRITICO: {e} ---")

