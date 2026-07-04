from flask import Flask, request
import text_logic
import media_logic
import doc_logic


app = Flask(__name__)
## TODOS? switch to waitress

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    if not payload or payload.get('event') != 'messages.upsert':
        return "OK", 200

    data = payload.get('data', {})
    msg_type = data.get('messageType')

    # SMISTAMENTO
    if msg_type == 'conversation':
        # Manda al gestore testi
        text_logic.process_text(data)
        
    if msg_type == 'imageMessage':
        # Manda al gestore media
        media_logic.process_media(data)

    elif msg_type == 'documentMessage':
        doc_logic.process_document(data)

    return "OK", 200

if __name__ == '__main__':
    app.run(port=8080, debug=False)