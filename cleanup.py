import os
import time

folder = "tmp"

def clean_all():
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

if __name__ == "__main__":
    print("ATTENZIONE: Questa operazione eliminerà TUTTI i dati nel DB e i file nelle cartelle:")
    print(f"Cartelle: {folder}")
    
    time.sleep(10)
    clean_all()