import os
from docx2pdf import convert
import config

# Cartella da scansionare
DOCS_FOLDER = config.Doc_path

def convert_all_in_folder():
    """Scansiona la cartella DOCUMENTS e converte tutti i .doc/.docx in .pdf"""
    
    if not os.path.exists(DOCS_FOLDER):
        print(f"--- [ERRORE] Cartella '{DOCS_FOLDER}' non trovata. ---")
        return

    # Trova tutti i file che finiscono per .doc o .docx
    files = [f for f in os.listdir(DOCS_FOLDER) if f.lower().endswith(('.doc', '.docx'))]
    
    if not files:
        print("--- [INFO] Nessun file Word da convertire. ---")
        return

    print(f"--- [INFO] Trovati {len(files)} file da convertire. ---")

    for filename in files:
        file_path = os.path.join(DOCS_FOLDER, filename)
        
        # Crea il nome del file PDF (sostituisce l'estensione)
        base_name = os.path.splitext(filename)[0]
        pdf_name = f"{base_name}.pdf"
        pdf_path = os.path.join(DOCS_FOLDER, pdf_name)
        
        # Controllo di sicurezza: non convertire se il PDF esiste già
        if os.path.exists(pdf_path):
            print(f"--- [SKIP] {pdf_name} esiste già. ---")
            continue
            
        try:
            print(f"--- [CONVERSIONE] {filename} -> {pdf_name} ---")
            convert(file_path, pdf_path)
            print(f"--- [OK] Convertito: {pdf_name} ---")
        except Exception as e:
            print(f"--- [ERRORE] Impossibile convertire {filename}: {e} ---")

if __name__ == "__main__":
    convert_all_in_folder()
    print("--- [FINE] Operazione completata. ---")