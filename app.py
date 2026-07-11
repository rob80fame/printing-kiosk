import threading
import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
from psycopg2.extras import RealDictCursor
import sv_ttk
import config
import os
import fitz
from PIL import Image, ImageTk
import subprocess
import sys
import time
from typing import Optional
from doc_logic import merge_docs

DB_CONFIG = config.DB_CONFIG

in_t = config.in_t

class FileLookupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Lookup & Print")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda event: self.root.destroy())

        self.current_code = None
        self.current_files = []
        self.current_file_index = 0
        self.tprice = tk.StringVar(value="€ 0.00")

        self.selected_files = set()
        self.is_selection_mode = False
        
        self.price_label_widget: Optional[ttk.Label] = None
        self.title_label: Optional[ttk.Label] = None
        self.btn_print_multi: Optional[ttk.Button] = None
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
        if getattr(self, 'inactivity_timer', None) is not None:
            self.root.after_cancel(self.inactivity_timer)
            self.inactivity_timer = None

    def reset_inactivity_timer(self, event=None):
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
            text="Stampa i tuoi documenti",
            font=("Segoe UI", 32, "bold")
        )
        title.pack(pady=(0, 40))

        # Instructions
        instructions = ttk.Label(
            container,
            text="Inserisci il codice fornito",
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
    
    def open_settings_manager(self):
            try:
                command = [sys.executable, "configuration_ui.py"]
                subprocess.Popen(command) 
            
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile avviare il processo di customizzazione: {str(e)}")

    def search_by_code(self):
        code = self.code_var.get().strip()
        self.CURR_CODE = code
        if not code:
            self.status_var.set("Inserisci un codice valido")
            return
        if code == config.sudo:
            self.open_settings_manager()
            self.code_var.set("")
            return
        elif code == config.shutp:
            self.root.destroy()
            return

        self.status_var.set("Ricerca in corso...")
        self.root.update()

        threading.Thread(target=self._search_worker, args=(code,), daemon=True).start()
    
    def print_current_file(self, file_path=None):
        command = [sys.executable, "print.py", file_path, self.CURR_CODE]
        server_proc = subprocess.Popen(command) 

        if server_proc.poll() is not None:
            code = self.CURR_CODE
            costt = config.readtmpprice(code)
            self.tprice.set(costt)
        
    def update_price(self):
        code = self.CURR_CODE
        costt = config.readtmpprice(code)
        self.tprice.set(costt)

        self.root.after(3000, self.update_price)

    def on_press(self, file_path):
        self.start_time = time.time()
        self.long_press_timer = self.root.after(800, lambda: self.activate_selection_mode())

    def activate_selection_mode(self):
        self.is_selection_mode = True
        
        if self.btn_print_multi and self.price_label_widget:
            self.btn_print_multi.pack(pady=10, before=self.price_label_widget)
            
        if self.title_label:
            self.title_label.config(text="Seleziona i file da stampare")

    def on_release(self, file_path, card):
        if self.long_press_timer:
            self.root.after_cancel(self.long_press_timer)
            self.long_press_timer = None

        if self.is_selection_mode:
            self.toggle_selection(file_path, card)
        else:
            if time.time() - self.start_time < 0.5:
                self.print_current_file_path(file_path)

    def toggle_selection(self, file_path, card):
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            card.configure(style="Normal.TFrame")
        else:
            self.selected_files.add(file_path)
            card.configure(style="Selected.TFrame")

    def print_multiple_files(self):
        filelist = self.selected_files
        tmpfile = merge_docs(filelist)
        self.print_current_file_path(tmpfile)

    def execute_multi_print(self):
        self.print_multiple_files()
        
        self.is_selection_mode = False
        self.selected_files.clear()
        
        if self.btn_print_multi is not None:
            self.btn_print_multi.pack_forget()
        
        if self.title_label is not None:
            self.title_label.config(text="File trovati")
    
    def torna_indietro_al_codice(self):
        self.selected_files.clear()
        self.show_code_input_screen()
            
    def show_carousel(self, file_list):
        self.clear_main_frame()

        self.start_inactivity_timer()
        self.main_frame.bind_all("<Motion>", self.reset_inactivity_timer)
        self.main_frame.bind_all("<Button-1>", self.reset_inactivity_timer)

        style = ttk.Style()
        style.configure("Normal.TFrame", background="#f0f0f0")
        style.configure("Selected.TFrame", background="#a8d8ff")

        # Back
        back_btn = ttk.Button(self.main_frame, text="← Torna al Codice", command=self.show_code_input_screen)
        back_btn.pack(anchor="nw", padx=10, pady=10)
        
        # Title
        ttk.Label(self.main_frame, text="File trovati", font=("Segoe UI", 20, "bold")).pack(pady=10)

        # Scrollbar and Canvas
        canvas = tk.Canvas(self.main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # 4 column
        cols = 4

        for i, file_path in enumerate(file_list):
            name = os.path.basename(file_path)
            row = i // cols
            col = i % cols
            
            card = ttk.Frame(scrollable_frame, padding=5, style="Normal.TFrame")
            card.grid(row=row, column=col, padx=5, pady=5)

            def toggle_select(event, c=card, p=file_path):
                if p in self.selected_files:
                    self.selected_files.remove(p)
                    c.configure(style="Normal.TFrame")
                else:
                    self.selected_files.add(p)
                    c.configure(style="Selected.TFrame")

            try:
                doc = fitz.open(file_path)
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                photo = ImageTk.PhotoImage(img)
                
                lbl_preview = ttk.Label(card, image=photo, cursor="hand2")
                lbl_preview.image = photo # type: ignore
                lbl_preview.pack()
                lbl_preview.bind("<ButtonPress-1>", lambda e, p=file_path: self.on_press(p))
                lbl_preview.bind("<ButtonRelease-1>", lambda e, p=file_path, c=card: self.on_release(p, c))            
            except Exception:
                ttk.Label(card, text="[Err]", width=15).pack()

            # Filename
            lbl_name = ttk.Label(card, text=name[:15], font=("Segoe UI", 8), background="#f0f0f0")
            lbl_name.pack()

            card.bind("<Button-1>", toggle_select)
            lbl_name.bind("<Button-1>", toggle_select)

        # Footer price
        self.price_label_widget = ttk.Label(self.main_frame, textvariable=self.tprice, font=("Segoe UI", 28, "bold"))
        self.price_label_widget.pack(side="bottom", anchor="w", padx=10, pady=10)

        # Print selected button
        self.btn_print_multi = ttk.Button(self.main_frame, text="Stampa Selezionati", command=self.execute_multi_print)
        
        self.update_price()

    def print_current_file_path(self, file_path):
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
        self.code_var.set("")
        
        cursor.close()
        conn.close()

        if results:
            record = results[0]
            
            file_list = record['file_paths']
            self.show_carousel(file_list)


def main():
    root = tk.Tk()
    sv_ttk.set_theme("light")

    app = FileLookupApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
    
