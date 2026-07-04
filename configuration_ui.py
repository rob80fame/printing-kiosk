import tkinter as tk
from tkinter import ttk, messagebox
import win32print  # Per elencare le stampanti
import sv_ttk
import json
import cleanup
import os


class PrinterSetupApp:
    def __init__(self, root):
        self.root = root
        
        self.root.title("Configurations")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda event: self.root.destroy())
        sv_ttk.set_theme("light")
        
        # Unico contenitore principale
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill="both", expand=True)

        # Bottone Chiudi
        ttk.Button(self.main_frame, text="✕ Chiudi", command=root.destroy).pack(anchor="nw")

        # Titolo
        ttk.Label(self.main_frame, text="Configurazione Parametri", font=("Segoe UI", 16, "bold")).pack(pady=10)

        # Selezione Stampante
        ttk.Label(self.main_frame, text="Seleziona Stampante:").pack(pady=(10, 0))
        self.printer_var = tk.StringVar()
        self.combo_printers = ttk.Combobox(self.main_frame, textvariable=self.printer_var, state="readonly")
        self.combo_printers['values'] = self.get_printers()
        self.combo_printers.pack(fill="x", pady=(0, 10))
        try:
            self.combo_printers.set(win32print.GetDefaultPrinter())
        except:
            pass

        # Creazione dei 5 campi richiesti
        self.fields = {} 
        labels = ["Password (pass)", "Directory NPM (npmdir)", "Nome (name)", "Numero Telefono (phonenum)", "API Key (apikey)"]
        keys = ["pass", "npmdir", "name", "phonenum", "apikey"]

        for label_text, key in zip(labels, keys):
            ttk.Label(self.main_frame, text=label_text).pack(anchor="w", padx=20)
            var = tk.StringVar()
            # Se è il campo password, potresti voler aggiungere show="*"
            show_char = "*" if key == "pass" else ""
            entry = ttk.Entry(self.main_frame, textvariable=var, show=show_char)
            entry.pack(fill="x", padx=20, pady=(0, 10))
            self.fields[key] = var

        # Bottoni Azioni
        ttk.Button(self.main_frame, text="Cancella dati temporanei", command=self.do_extra_action).pack(fill="x", pady=5)
        ttk.Button(self.main_frame, text="Salva Configurazione", style="Accent.TButton", command=self.save).pack(fill="x", pady=10)


    def get_printers(self):
        """Recupera la lista delle stampanti installate"""
        printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        return printers

    def do_extra_action(self):
        cleanup.clean_all()
        messagebox.showinfo("Pulizia", f"Pulizia eseguita")

    def save(self):
        config_path = 'config.json'
        
        # 1. Carica la configurazione attuale se esiste, altrimenti inizializza un dizionario vuoto
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        else:
            data = {}

        # 2. Aggiorna la stampante
        data['Printer'] = self.printer_var.get()

        # 3. Aggiorna gli altri campi solo se il valore nell'Entry non è vuoto
        for key, var in self.fields.items():
            valore_inserito = var.get().strip()
            if valore_inserito:  # Se la stringa non è vuota
                data[key] = valore_inserito

        # 4. Salva il file aggiornato
        try:
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Successo", "Configurazione salvata correttamente!")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare il file: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PrinterSetupApp(root)
    root.mainloop()