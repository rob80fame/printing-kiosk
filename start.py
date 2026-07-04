import app
import config
import backend
import cleanup

import subprocess
import os
import threading
import sys


npm_dir = config.npm_dir
py_dir = sys.executable

processes = []

def clean_all():
    backend.cleanup.clean_all()
    cleanup.clean_all()

def start_service(command, directory):
    p = subprocess.Popen(
        command,
        cwd=directory,
        shell=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    processes.append(p)
    return p

def stop_all():
    print("\n--- Terminazione in corso ---")
    for p in processes:
        try:
            subprocess.run(f"taskkill /F /T /PID {p.pid}", shell=True, capture_output=True)
        except Exception as e:
            print(f"Errore nella chiusura del processo {p.pid}: {e}")
    os._exit(0)

def start_all():
    start_service("npm.cmd start", os.path.join(config.Proj_path, "evolution-api"))
    start_service("python.exe backend.py", config.Proj_path)
    
    print("Servizi avviati. Premi INVIO per chiudere tutto.")
    
    threading.Thread(target=lambda: [input(), stop_all()], daemon=True).start()
    
    try:
        app.main()
    finally:
        stop_all()

if __name__ == "__main__":
    start_all()