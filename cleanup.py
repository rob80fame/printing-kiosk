import os
import psycopg2
import config
import json

# --- CONFIGURAZIONE ---
DB_CONFIG = config.DB_CONFIG

# Aggiungi qui i nomi delle cartelle che vuoi pulire
FOLDERS_TO_CLEAN = ["IMAGES", "DOCUMENTS", "tmp"]

def clean_all():
    # 1. Pulizia Database
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE orders RESTART IDENTITY;")
        conn.commit()
        cur.close()
        conn.close()
        print("--- [CLEANUP] Database pulito con successo ---")
    except Exception as e:
        print(f"--- [CLEANUP] Errore Database: {e} ---")

    # 2. Pulizia Cartelle
    for folder in FOLDERS_TO_CLEAN:
        if os.path.exists(folder):
            # Otteniamo la lista dei file
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

    # 3. Pulizia Tmp
    try:
        with open(config.FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4)
        print("File tmp.json pulito con successo.")
    except Exception as e:
        print(f"Errore durante la pulizia del file: {e}")

if __name__ == "__main__":
    clean_all()