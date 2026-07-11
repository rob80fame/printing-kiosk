import os
import requests
from docx2pdf import convert
import text_logic
import db_manager
from crypto_utils import decrypt_whatsapp_media
import config
import fitz
import uuid

DOWNLOAD_FOLDER = config.Doc_path

if not os.path.exists(DOWNLOAD_FOLDER): 
    os.makedirs(DOWNLOAD_FOLDER)

def process_document(data):
    
    mittente = data.get('key', {}).get('remoteJid')
    msg_content = data.get('message', {})
    doc_data = msg_content.get('documentMessage', {})
    
    if not doc_data or 'url' not in doc_data or 'mediaKey' not in doc_data:
        return

    media_key = doc_data.get('mediaKey')
    msg_id = data.get('key', {}).get('id')

    file_name = doc_data.get('fileName', f"doc_{msg_id}.docx")
    
    file_path = os.path.join(DOWNLOAD_FOLDER, file_name)

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
                pdf_path = os.path.join(DOWNLOAD_FOLDER, f"{base_name}.pdf")
                
                print(f"--- [DOC] Conversione in PDF in corso... ---")
                try:
                    convert(file_path, pdf_path)
                    print(f"--- [DOC] Conversione riuscita: {pdf_path} ---")
                    final_path = pdf_path # Aggiorniamo il path al PDF
                except Exception as conv_err:
                    print(f"--- [DOC] Errore conversione PDF: {conv_err} ---")
            
            code = db_manager.register_or_append_file(mittente, final_path)
            text_logic.invia_risposta(mittente, f"Documento ricevuto! Il tuo codice è: {code}")
            
        else:
            print(f"--- [DOC] Errore download. Status: {resp.status_code} ---")
            
    except Exception as e:
        print(f"--- [DOC] ERRORE CRITICO: {e} ---")

def merge_docs(selected_files):
    
    tmp_dir = os.path.join(os.getcwd(), "tmp")
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    unique_id = uuid.uuid4().hex[:8]
    filename = f"stampa_{unique_id}.pdf"
    output_path = os.path.join(tmp_dir, filename)
    
    doc_unito = fitz.open()

    for f in sorted(list(selected_files)):
        if os.path.exists(f):
            try:
                with fitz.open(f) as doc_corrente:
                    doc_unito.insert_pdf(doc_corrente)
            except Exception as e:
                print(f"Errore nell'unire il file {f}: {e}")

    doc_unito.save(output_path)
    doc_unito.close()

    return output_path