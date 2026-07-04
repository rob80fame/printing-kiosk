import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

def decrypt_whatsapp_media(enc_data, media_key_input, media_type):
    """Decrittazione standard rimuovendo i 10 byte del MAC."""
    
    # 1. Conversione chiave
    if isinstance(media_key_input, dict):
        media_key = bytes([media_key_input[str(i)] for i in range(len(media_key_input))])
    else:
        try:
            media_key = base64.b64decode(media_key_input)
        except:
            media_key = media_key_input
    
    # 2. Setup AES (Derivazione Chiave)
    app_info = f"WhatsApp {media_type} Keys"
    hkdf = HKDF(algorithm=hashes.SHA256(), length=112, salt=None, info=app_info.encode('utf-8'), backend=default_backend())
    expanded = hkdf.derive(media_key)
    iv, cipher_key = expanded[0:16], expanded[16:48]
    
    # 3. RIMUOVI I 10 BYTE DEL MAC
    # Questo è il passaggio cruciale che risolve l'errore del "multiplo di blocco"
    encrypted_data_clean = enc_data[:-10]
    
    # 4. Decrittazione
    cipher = Cipher(algorithms.AES(cipher_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    # Decifriamo i dati puliti (senza MAC)
    data = decryptor.update(encrypted_data_clean) + decryptor.finalize()
    
    # 5. Unpadding (Gestisce i byte di riempimento standard AES)
    try:
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(data) + unpadder.finalize()
    except: 
        # Se il file non ha padding, lasciamolo così com'è
        pass 
    
    return data