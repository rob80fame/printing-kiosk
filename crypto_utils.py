import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

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