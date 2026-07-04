import threading
import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
from psycopg2.extras import RealDictCursor
import sv_ttk
from backend import config
import os
import fitz
from PIL import Image, ImageTk
import subprocess
import sys
# Database configuration
DB_CONFIG = config.DB_CONFIG
in_t = 50000 #(sec in millisec)

class FileLookupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Lookup & Print")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda event: self.root.destroy())

        self.current_code = None
        self.current_files = []
        self.current_file_index = 0

        self.inactivity_timer = None

        self.build_ui()
        self.show_code_input_screen()

    def build_ui(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

    def start_inactivity_timer(self):
        self.stop_inactivity_timer()
        self.inactivity_timer = self.root.after(in_t, self.show_code_input_screen)

    def stop_inactivity_timer(self):
        """Ferma il timer esistente"""
        if self.inactivity_timer:
            self.root.after_cancel(self.inactivity_timer)
            self.inactivity_timer = None

    def reset_inactivity_timer(self, event=None):
        """Resetta il timer (chiamato ad ogni interazione)"""
        self.start_inactivity_timer()
    
    def show_code_input_screen(self):

        self.stop_inactivity_timer()
        self.main_frame.unbind_all("<Motion>")
        self.main_frame.unbind_all("<Button-1>")
        self.clear_main_frame()

        container = ttk.Frame(self.main_frame, padding=40)
        container.pack(expand=True)

        # Title
        title = ttk.Label(
            container,
            text="Ricerca File",
            font=("Segoe UI", 32, "bold")
        )
        title.pack(pady=(0, 40))

        # Instructions
        instructions = ttk.Label(
            container,
            text="Inserisci il codice per cercare i file",
            font=("Segoe UI", 14),
            foreground="#666666"
        )
        instructions.pack(pady=(0, 20))

        # Code input frame
        input_frame = ttk.Frame(container)
        input_frame.pack(fill="x", padx=100, pady=20)

        ttk.Label(input_frame, text="Codice:", font=("Segoe UI", 14)).pack(side="left", padx=(0, 10))
        
        self.code_var = tk.StringVar()
        code_entry = ttk.Entry(
            input_frame,
            textvariable=self.code_var,
            font=("Segoe UI", 16),
            width=20
        )
        code_entry.pack(side="left", padx=5)
        code_entry.focus()
        code_entry.bind("<Return>", lambda e: self.search_by_code())

        # Search button
        search_btn = ttk.Button(
            container,
            text="Cerca",
            command=self.search_by_code,
            style="Accent.TButton",
        )
        search_btn.pack(pady=20)

        # Status
        self.status_var = tk.StringVar(value="")
        status_label = ttk.Label(
            container,
            textvariable=self.status_var,
            foreground="#041B57",
            font=("Segoe UI", 16)
        )
        status_label.pack(pady=(20, 0))

    def clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def search_by_code(self):
        code = self.code_var.get().strip()
        #print(code)
        if not code:
            self.status_var.set("Inserisci un codice valido")
            return

        self.status_var.set("Ricerca in corso...")
        self.root.update()

        threading.Thread(target=self._search_worker, args=(code,), daemon=True).start()
    
    def print_current_file(self, file_path=None):
        try:
            command = [sys.executable, "print.py", file_path]
            subprocess.Popen(command) 
            #messagebox.showinfo("Successo", f"Stampa inviata: {os.path.basename(file_path)}")
        
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile avviare il processo di stampa: {str(e)}")

    def show_carousel(self, file_list):

        self.clear_main_frame()
        
        # Avvia il monitoraggio dell'inattività appena entri nel carousel
        self.start_inactivity_timer()
        
        # Se l'utente muove il mouse o clicca, resetta il timer
        self.main_frame.bind_all("<Motion>", self.reset_inactivity_timer)
        self.main_frame.bind_all("<Button-1>", self.reset_inactivity_timer)

        # --- Aggiunta Pulsante Back ---
        back_btn = ttk.Button(self.main_frame, text="← Torna al Codice", 
                              command=self.show_code_input_screen)
        back_btn.pack(anchor="nw", padx=10, pady=10)
        
        # Titolo
        ttk.Label(self.main_frame, text="File trovati", font=("Segoe UI", 20, "bold")).pack(pady=10)

        # Scrollbar e Canvas per la griglia
        canvas = tk.Canvas(self.main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # Griglia 4 colonne
        cols = 4
        for i, file_path in enumerate(file_list):
            row = i // cols
            col = i % cols
            
            # Card per ogni file
            card = ttk.Frame(scrollable_frame, padding=5)
            card.grid(row=row, column=col, padx=5, pady=5)

            # Anteprima
            try:
                doc = fitz.open(file_path)
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.3, 0.3)) # Miniatura piccola
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                photo = ImageTk.PhotoImage(img)
                
                btn = ttk.Button(card, image=photo, command=lambda p=file_path: self.print_current_file_path(p))
                btn.image = photo
                btn.pack()
            except Exception:
                ttk.Button(card, text="[Anteprima non disp.]", width=15, 
                           command=lambda p=file_path: self.print_current_file_path(p)).pack()

            # Nome file (troncato per non rompere il layout)
            name = os.path.basename(file_path)
            ttk.Label(card, text=name[:15] + "...", font=("Segoe UI", 8)).pack()

    def print_current_file_path(self, file_path):
        """Metodo richiamato dal bottone di stampa del carousel"""
        self.current_files = [file_path]
        self.current_file_index = 0
        self.print_current_file(file_path)

    def _search_worker(self, code):
        conn = None
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT code, file_paths
            FROM orders
            WHERE code = %s
            ORDER BY created_at DESC
        """
        cursor.execute(query, (code,))
        results = cursor.fetchall()

        if len(results) == 0:
            self.status_var.set("Codice errato")
            cursor.close()
            conn.close()
            return
        
        self.status_var.set("Trovato i tuoi file")
        
        cursor.close()
        conn.close()

        if results:
            record = results[0]
            
            #code = record['code']
            file_list = record['file_paths']
            self.show_carousel(file_list)
            #return file_list


def main():
    root = tk.Tk()
    sv_ttk.set_theme("light")

    app = FileLookupApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
    
