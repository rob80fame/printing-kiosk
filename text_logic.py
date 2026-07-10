import requests
import config
import cleanup

# Configurazione API
API_URL = "http://localhost:8080"
INSTANCE = config.instance_name
API_KEY = config.apikey

def process_text(data):
    msg_content = data.get('message', {}).get('conversation', "").strip().lower()
    mittente = data.get('key', {}).get('remoteJid')
    
    print(f"--- [TESTO] Ricevuto: {msg_content} ---")
    
    if msg_content == "pulisci":
        cleanup.clean_all()
        invia_risposta(mittente, f"cleared")


def invia_risposta(destinatario, testo):
    url = f"{API_URL}/message/sendText/{INSTANCE}"
    headers = {"apikey": API_KEY, "Content-Type": "application/json"}
    requests.post(url, json={"number": destinatario, "text": testo}, headers=headers)
    print(f"--- [TESTO] Risposta inviata ---")