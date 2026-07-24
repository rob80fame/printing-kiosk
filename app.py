import os
import sys
import base64
import asyncio
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
from nicegui import ui
import json
import uuid
import fitz
import base64
from PIL import Image
from io import BytesIO
import platform

with open('config.json', 'r') as f:
    file = json.load(f)

# Configurazione
db_pass = file['pass']
PRINTER_NAME = file['Printer']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

PRICES = file['prices']
FOLDERS_TO_CLEAN = ["IMAGES", "DOCUMENTS", "tmp"]

class PrintingKiosk:
    def __init__(self):
        self.current_code = ""
        self.selected_files = set()
        self.totalprice = "€ 0.00"
        self.preview_area = None
        self.is_updating = False
        self.price_label = None

        self.config = {
            'copies': 1,
            'mode': 'Bianco e Nero',
            'duplex': 'Fronte-Retro',
            'layout': 'Uno per foglio',
            'pages': 'Tutte',
            'format': 'A4'
        }

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
            #ui.notify("Codice errato", type='warning')
            cursor.close()
            conn.close()
            return
        
        #ui.notify("Trovato i tuoi file", type='positive')
        cursor.close()
        conn.close()

        if results:
            record = results[0]
            file_list = record['file_paths']
            return file_list

    async def search_by_code(self, code, container):
        if not code:
            ui.notify("Inserisci un codice valido", type='warning')
            return
        if code == file['sudo']:
            self.render_configuration_ui(container, lambda: app_instance.render_login(container))
            return
        elif code == file['shutp']:
            ui.run_javascript('window.close()')
            ui.timer(1.0, lambda: sys.exit())
            return
        else:
            self.current_code = code
            results = await asyncio.to_thread(self._search_worker, code)
            if not results:
                #ui.notify("Codice errato", type='negative')
                return
            container.clear()
            with container:
                self.render_file_grid(results, container)

    def render_login(self, container):
        container.clear()
        with container:
            ui.label("Stampa i tuoi documenti").classes('mt-70 text-4xl font-bold mb-2')
            ui.label("Inserisci il codice mandato su Whatsapp").classes('text-xl mb-8')
            code_input = ui.input(label="Codice").classes('w-64 text-2xl')
            code_input.on('keydown.enter', lambda: self.search_by_code(code_input.value, container))
            ui.button("Cerca", on_click=lambda: self.search_by_code(code_input.value, container)).classes('mt-5 px-20')

    def render_file_grid(self, file_list, container):
        container.clear()
        # Nota: container viene passato qui per aggiungere elementi
        ui.button("← Indietro", on_click=lambda: self.render_login(container)).classes('self-start')
        ui.label("File trovati").classes('text-2xl font-bold my-5')
        
        with ui.grid(columns=4).classes('gap-4'):
            for f in file_list:
                preview_data = self.get_pdf_preview_data(f)
                
                # Creiamo la card
                with ui.card().classes('w-64 h-64 border p-2 cursor-pointer bg-white transition-all') as card:
                    # Al click, eseguiamo il toggle
                    card.on('click', lambda f=f, c=card: self.toggle_selection(f, c))
                    
                    if preview_data:
                        ui.image(preview_data).classes('w-full h-full object-contain pointer-events-none')
                    
                    ui.label(os.path.basename(f)[:15]).classes('text-xs pointer-events-none')

        ui.button("Stampa", on_click=lambda: self.print_selected_files(container)).classes('mt-10 bg-green-600')
        with ui.row().classes('w-full justify-end mt-10'):
            self.price_label = ui.label(self.totalprice).classes('text-2xl font-bold text-green-700')
        
        # Timer che chiama update_cost ogni 3 secondi
        ui.timer(3.0, self.update_cost)


    def toggle_selection(self, file_path, card):
        # Definiamo le classi base
        base_classes = 'w-64 h-64 border p-2 cursor-pointer transition-all'
        
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            # Ritorna allo stato normale (bianco)
            card.classes(replace=f'{base_classes} bg-white')
        else:
            self.selected_files.add(file_path)
            # Cambia stato in "selezionato" (azzurro)
            card.classes(replace=f'{base_classes} bg-blue-300')

    def compute_cost(self):
        """Calcola il costo basandosi sulla configurazione corrente."""
        if not os.path.exists(os.path.join(os.getcwd(), 'DOCUMENTS')):
            return 0.0
            
        # Determina numero pagine totali
        # (Assumiamo di aprire il file temporaneo o originale per contare)
        try:
            with fitz.open(self.current_file_path) as d: # Assicurati di salvare il percorso corrente
                total_pages = len(d)
        except:
            return 0.0

        selected = self.parse_page_selection(self.config['pages'], total_pages)
        pages_to_print = len(selected)
        copies = int(self.config['copies'])
        size = self.config['format']
        is_color = (self.config['mode'] == "Colore")
        is_duplex = (self.config['duplex'] == "Fronte-Retro")
        layout = self.config['layout']

        # Logica pagine per foglio
        pages_per_sheet = 2 if layout == "Due per foglio" else 4 if layout == "Quattro per foglio" else 1
        if is_duplex:
            pages_per_sheet *= 2
        
        sheets_per_copy = (pages_to_print + pages_per_sheet - 1) // pages_per_sheet

        # Recupero prezzi
        pricing = PRICES["color"] if is_color else PRICES["bw"]
        page_price = pricing.get(size, pricing["A4"])
        duplex_price = pricing.get("duplex_price", {}).get(size, page_price)

        if is_duplex:
            duplex_sheets = pages_to_print // pages_per_sheet
            leftover_pages = pages_to_print % pages_per_sheet
            base_cost = (duplex_sheets * duplex_price + leftover_pages * page_price) * copies
        else:
            base_cost = page_price * sheets_per_copy * copies

        return round(base_cost + 1e-9, 2)

    def update_cost(self):
        """Aggiorna il costo visualizzato nell'interfaccia."""
        self.totalprice = readtmpprice(self.current_code)  
        if self.price_label:
            self.price_label.set_text(self.totalprice)

    def prepare_print_pdf(self, file_path):
        """Prepara il file PDF applicando layout e selezioni[cite: 2]."""
        selected_pages = self.parse_page_selection(self.config['pages'], len(fitz.open(file_path)))
        
        input_doc = fitz.open(file_path)
        output_doc = fitz.open()
        
        # Logica di layout[cite: 2]
        layout_val = self.config['layout']
        if layout_val in ("Due per foglio", "Quattro per foglio"):
            pages_per_sheet = 2 if layout_val == "Due per foglio" else 4
            cols = 2 if pages_per_sheet > 1 else 1
            rows = pages_per_sheet // cols
            i = 0
            while i < len(selected_pages):
                group_indexes = selected_pages[i:i+pages_per_sheet]
                imgs = []
                for page_num in group_indexes:
                    idx = page_num - 1
                    page = input_doc[idx]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    if pix.n < 4:
                        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    else:
                        img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples).convert("RGB")
                    imgs.append(img)

                while len(imgs) < pages_per_sheet:
                    if imgs:
                        w0, h0 = imgs[0].size
                    else:
                        w0, h0 = (100, 100)
                    imgs.append(Image.new("RGB", (w0, h0), (255, 255, 255)))

                tile_w = max(im.width for im in imgs)
                tile_h = max(im.height for im in imgs)
                combined_w = tile_w * cols
                combined_h = tile_h * rows
                combined = Image.new("RGB", (combined_w, combined_h), (255, 255, 255))

                for idx_img, im in enumerate(imgs):
                    col = idx_img % cols
                    row = idx_img // cols
                    im_resized = im.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
                    combined.paste(im_resized, (col * tile_w, row * tile_h))

                buf = BytesIO()
                combined.save(buf, format="PNG")
                img_bytes = buf.getvalue()

                rect = fitz.Rect(0, 0, combined.width, combined.height)
                page = output_doc.new_page(width=combined.width, height=combined.height)
                page.insert_image(rect, stream=img_bytes)

                i += pages_per_sheet
        else:
            for page_num in selected_pages:
                output_doc.insert_pdf(input_doc, from_page=page_num, to_page=page_num)

        tmp_path = os.path.join("tmp", f"print_{uuid.uuid4().hex[:6]}.pdf")
        output_doc.save(tmp_path)
        input_doc.close()
        output_doc.close()
        return tmp_path

    def merge_docs(self, file_list):
        tmp_dir = os.path.join(os.getcwd(), "tmp")
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        unique_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(tmp_dir, f"stampa_{unique_id}.pdf")
        
        doc_unito = fitz.open()

        for f in sorted(list(file_list)):
            if not os.path.exists(f):
                continue
                
            ext = os.path.splitext(f)[1].lower()
            
            try:
                if ext == ".pdf":
                    with fitz.open(f) as doc:
                        doc_unito.insert_pdf(doc)
                
                elif ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                    img_doc = fitz.open()
                    img = fitz.open(f)
                    rect = img[0].rect
                    pdfbytes = img.convert_to_pdf()
                    img_pdf = fitz.open("pdf", pdfbytes)
                    doc_unito.insert_pdf(img_pdf)
                    img.close()
                    img_doc.close()
                
                else:
                    print(f"Formato non supportato: {ext}")
                    
            except Exception as e:
                print(f"Errore durante l'elaborazione di {f}: {e}")

        doc_unito.save(output_path)
        doc_unito.close()
        return output_path

    def print_selected_files(self, container):
        if not self.selected_files:
            ui.notify("Seleziona almeno un file!", type='warning')
            return
        tmp_file = self.merge_docs(list(self.selected_files))
        self.render_print_config(container, tmp_file)
        
        # Reset selezione dopo la stampa (opzionale)
        self.selected_files.clear()
        # Se vuoi aggiornare la UI, ricarica la griglia
        # ...
            
    def get_pdf_preview_data(self, file_path):
        try:
            # Apri il documento
            doc = fitz.open(file_path)
            # Ottieni la prima pagina
            page = doc.load_page(0)
            # Genera il pixmap con la scala richiesta
            pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
            
            # Converti il pixmap in bytes PNG (più veloce di PIL)
            png_bytes = pix.tobytes("png")
            
            # Codifica in base64
            base64_string = base64.b64encode(png_bytes).decode('utf-8')
            
            # Ritorna il Data URI
            return f"data:image/png;base64,{base64_string}"
        except Exception as e:
            print(f"Errore preview {file_path}: {e}")
            return None # Oppure un'immagine di placeholder

    def get_printers(self):
        """Recupera la lista delle stampanti di sistema per Windows e Linux."""
        system = platform.system()

        # --- LOGICA WINDOWS ---
        if system == "Windows":
            try:
                import win32print
                return [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            except ImportError:
                print("Modulo win32print non trovato.")
                return []
            except Exception as e:
                print(f"Errore stampanti Windows: {e}")
                return []

        # --- LOGICA LINUX ---
        elif system == "Linux":
            try:
                # Esegue 'lpstat -p' per ottenere la lista delle stampanti configurate
                # L'output tipico è: "printer NomeStampante is idle"
                output = subprocess.check_output(['lpstat', '-p'], text=True)
                printers = []
                for line in output.splitlines():
                    if line.startswith("printer"):
                        # Estrae il nome della stampante (la seconda parola)
                        parts = line.split()
                        if len(parts) > 1:
                            printers.append(parts[1])
                return printers
            except Exception as e:
                print(f"Errore recupero stampanti Linux: {e}")
                return []

        return []
        
    def render_print_config(self, container, file_path):
        self.current_file_path = file_path
        container.clear()
        
        control_classes = 'w-full text-xl'

        # Contenitore principale a schermo intero
        with container.classes('w-full h-screen overflow-hidden'):
            # Split 50/50 per dividere lo schermo equamente
            with ui.splitter(value=50).classes('w-full h-full') as splitter:
                
                # --- LATO SINISTRO (Configurazione) ---
                with splitter.before:
                    with ui.column().classes('w-full h-full p-8 gap-4 overflow-y-auto'):
                        ui.button("← Indietro", on_click=lambda: self.render_login(container)).classes('self-start')
                        ui.label("Configurazione Stampa").classes('text-3xl font-bold mb-4')

                        ui.number("Copie", value=1, format='%.0f', on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'copies')
                        ui.select(["Bianco e Nero", "Colore"], label="Modalità", on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'mode')
                        ui.select(["A4", "A3", "A5"], label="Formato", on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'format')
                        ui.select(["Solo Fronte", "Fronte-Retro"], label="Fronte-Retro", on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'duplex')
                        ui.select(["Uno per foglio", "Due per foglio", "Quattro per foglio"], label="Layout", on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'layout')
                        ui.input("Pagine (es: 1-3, 5)", on_change=self.update_ui_elements).classes(control_classes).bind_value(self.config, 'pages')
                        
                        ui.separator().classes('my-4')
                        ui.button("STAMPA", on_click=lambda: self.send_to_printer(file_path, container)).classes('w-full py-6 text-3xl font-bold bg-green-600')
                        
                        # Salvato in self per update_ui_elements
                        self.cost_label = ui.label("€ 0.00").classes('text-4xl font-bold text-green-700 mt-2')

                # --- LATO DESTRO (Anteprima) ---
                with splitter.after:
                    # Contenitore principale a blocco fisso
                    with ui.column().classes('w-full h-full bg-gray-100 p-6 overflow-hidden'):
                        # Titolo fisso in alto (non scorre via)
                        ui.label("Anteprima").classes('text-2xl font-bold mb-4 shrink-0')
                        
                        # Area di scorrimento dedicata al touch per la preview
                        with ui.scroll_area().classes('w-full h-full'):
                            # Salvato in self per update_ui_elements e popolamento dinamico
                            self.preview_area = ui.column().classes('w-full items-center')

        # Trigger iniziale
        ui.timer(0.1, self.update_ui_elements, once=True)

    async def update_ui_elements(self, *args):
        if self.is_updating:
            return 
        
        self.is_updating = True
        try:
            # 1. Aggiorna il costo
            cost = self.compute_cost()
            if self.cost_label:
                self.cost_label.set_text(f"€ {cost:.2f}")
            
            # 2. Pulisci l'area di anteprima PRIMA di aggiungere lo spinner
            if self.preview_area:
                self.preview_area.clear()
                
                with self.preview_area:
                    # Mostra lo spinner temporaneamente
                    spinner = ui.spinner(size='lg')
                    
                    # Genera le immagini
                    images = await asyncio.to_thread(
                        self.generate_preview_images, 
                        self.current_file_path, 
                        self.config['mode'], 
                        self.config['layout'], 
                        self.config['pages']
                    )
                    
                    # Rimuovi lo spinner esplicitamente prima di mostrare le immagini
                    spinner.delete() 
                    
                    for img_b64 in images:
                        ui.image(f"data:image/png;base64,{img_b64}").classes('w-full h-auto object-contain border shadow-md mb-4')
        finally:
            self.is_updating = False


    def render_configuration_ui(self, container, on_back_callback):
        """
        container: Il contenitore ui.column() in cui disegnare
        on_back_callback: Funzione da chiamare per tornare indietro
        """
        container.clear()
        
        # Carica la configurazione attuale se esiste
        config_path = 'config.json'
        config_data = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            except:
                pass

        with container:
            ui.button("← Indietro", on_click=on_back_callback).classes('self-start')
            ui.label("Configurazione Parametri").classes('text-2xl font-bold mb-5')

            # Selezione Stampante
            printer_select = ui.select(
                options=self.get_printers(),
                label="Seleziona Stampante",
                value=config_data.get('Printer', '')
            ).classes('w-full max-w-md')

            # Campi configurazione
            # Struttura: key -> (label, password_field)
            field_definitions = {
                "pass": ("Password (pass)", True),
                "npmdir": ("Directory NPM (npmdir)", False),
                "name": ("Nome (name)", False),
                "phonenum": ("Numero Telefono (phonenum)", False),
                "apikey": ("API Key (apikey)", True),
                "mode": ("Mode (silence/send)", False)
            }
            
            inputs = {}
            with ui.column().classes('w-full max-w-md gap-2'):
                for key, (label, is_pass) in field_definitions.items():
                    inputs[key] = ui.input(
                        label=label, 
                        value=config_data.get(key, '')
                    ).props(f'type={"password" if is_pass else "text"}').classes('w-full')

            def save():
                data = config_data.copy()
                data['Printer'] = printer_select.value
                for key, ui_input in inputs.items():
                    val = ui_input.value.strip()
                    if val:
                        data[key] = val
                
                try:
                    with open(config_path, 'w') as f:
                        json.dump(data, f, indent=4)
                    ui.notify("Configurazione salvata con successo!", type='positive')
                except Exception as e:
                    ui.notify(f"Errore nel salvataggio: {e}", type='negative')

            def do_extra_action():
                self.clean_all()
                ui.notify("Pulizia eseguita", type='info')
            def shutdown():
                if platform.system() == "Linux":
                    os.system("sudo poweroff")
                elif platform.system() == "Windows":
                    os.system("shutdown /s /t 0")

            ui.button("Cancella dati temporanei", on_click=do_extra_action).classes('w-full max-w-md bg-red-500 mt-5')
            ui.button("Spegni il server", on_click=shutdown).classes('w-full max-w-md bg-red-500 mt-5')
            ui.button("Salva Configurazione", on_click=save).classes('w-full max-w-md bg-blue-600')

    def clean_all(self):
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

        for folder in FOLDERS_TO_CLEAN:
            if os.path.exists(folder):
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

        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4)
            print("File tmp.json pulito con successo.")
        except Exception as e:
            print(f"Errore durante la pulizia del file: {e}")

    def send_to_printer(self, file_path, container):
        if not os.path.exists(r"SumatraPDF.exe"):
            copies = self.config['copies']
            color_opt = "color" if self.config['mode'] == "Colore" else "monochrome"
            duplex_opt = "two-sided-long-edge" if self.config['duplex'] == "Fronte-Retro" else "one-sided"
            media_opt = self.config['format']
            cmd = ["lp", "-d", PRINTER_NAME, "-n", copies, "-o", f"color={color_opt}", "-o", f"sides={duplex_opt}", "-o", f"media={media_opt}", "-o", "fit-to-page", file_path ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                registertmpprice(self.current_code, self.cost_label.text)
                container.clear()
                self.render_login(container)
            except subprocess.CalledProcessError as e:
                print(f"Errore stampa (lp): {e.stderr}")
                return False
            except Exception as e:
                print(f"Errore generico: {e}")
                return False
        else:
            copies = self.config['copies']
            color_mode = "color" if self.config['mode'] == "Colore" else "monochrome"
            layout = "duplex" if self.config['duplex'] == "Fronte-Retro" else "simplex"
            print_settings = f"{copies}x,{color_mode},{self.config['format']},{layout},ignore-pdf-print-settings"
            cmd = ["SumatraPDF.exe", "-print-to", PRINTER_NAME, "-silent", "-print-settings", print_settings, file_path]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                registertmpprice(self.current_code, self.cost_label.text)
                container.clear()
                self.render_login(container)
            except subprocess.CalledProcessError as e:
                print(f"Errore stampa: {e}")
                return False
    
    def parse_page_selection(self, pages_str, total_pages):
        """Converte una stringa come '1-3, 5' in una lista di indici [0, 1, 2, 4]."""
        if not pages_str or pages_str.lower() in {"tutte", "all"}:
            return list(range(total_pages))
        
        selected = []
        try:
            for part in pages_str.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    selected.extend(range(start - 1, end))
                else:
                    selected.append(int(part) - 1)
            return [p for p in sorted(set(selected)) if 0 <= p < total_pages]
        except:
            return list(range(total_pages))

    def generate_preview_images(self, file_path, mode, layout, pages_str):
        """Genera anteprime (Base64) basate su impostazioni di stampa."""
        doc = fitz.open(file_path)
        total_pages = len(doc)
        page_indices = self.parse_page_selection(pages_str, total_pages)
        
        is_bw = (mode == "Bianco e Nero")
        images_base64 = []

        # Funzione helper per ottenere immagine pagina
        def get_img(page_idx):
            page = doc[page_idx]
            # Matrice di rendering (1.5 per una buona qualità/peso)
            matrix = fitz.Matrix(4, 4)
            if is_bw:
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples).convert("RGB")
            else:
                pix = page.get_pixmap(matrix=matrix)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            return img

        # Logica Layout
        if layout == "Uno per foglio":
            for idx in page_indices:
                img = get_img(idx)
                img.thumbnail((400, 600)) # Ridimensiona per web
                buf = BytesIO()
                img.save(buf, format="PNG")
                images_base64.append(base64.b64encode(buf.getvalue()).decode())

        elif layout == "Due per foglio":
            # Processa a coppie
            for i in range(0, len(page_indices), 2):
                img1 = get_img(page_indices[i])
                img2 = get_img(page_indices[i+1]) if (i+1) < len(page_indices) else None
                
                w = img1.width + (img2.width if img2 else 0)
                h = max(img1.height, img2.height if img2 else 0)
                combined = Image.new("RGB", (w, h), (255, 255, 255))
                combined.paste(img1, (0, 0))
                if img2: combined.paste(img2, (img1.width, 0))
                
                combined.thumbnail((600, 400))
                buf = BytesIO()
                combined.save(buf, format="PNG")
                images_base64.append(base64.b64encode(buf.getvalue()).decode())

        elif layout == "Quattro per foglio":
            # Processa a gruppi di 4
            for i in range(0, len(page_indices), 4):
                imgs = [get_img(page_indices[i+j]) if (i+j) < len(page_indices) else None for j in range(4)]
                
                tile_w = max(im.width for im in imgs if im)
                tile_h = max(im.height for im in imgs if im)
                combined = Image.new("RGB", (tile_w * 2, tile_h * 2), (255, 255, 255))
                
                positions = [(0, 0), (tile_w, 0), (0, tile_h), (tile_w, tile_h)]
                for k, im in enumerate(imgs):
                    if im:
                        im_resized = im.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
                        combined.paste(im_resized, positions[k])
                
                combined.thumbnail((500, 500))
                buf = BytesIO()
                combined.save(buf, format="PNG")
                images_base64.append(base64.b64encode(buf.getvalue()).decode())

        doc.close()
        return images_base64
        

Tmpjson = 'tmp.json'
def registertmpprice(user_id, amount_str):
    new_price = float(amount_str.replace('€', '').replace(',', '.').strip())
    
    if os.path.exists(Tmpjson):
        with open(Tmpjson, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    # 3. Calcola il nuovo totale
    if user_id in data:
        current_price_str = data[user_id].replace('€', '').replace(',', '.').strip()
        current_price = float(current_price_str)
        total = current_price + new_price
    else:
        total = new_price
    
    data[user_id] = f"€ {total:.2f}".replace('.', ',')
    
    with open(Tmpjson, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def readtmpprice(user_id):
    if not os.path.exists(Tmpjson):
        return "€ 0,00"
        
    with open(Tmpjson, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data.get(str(user_id), "€ 0,00")
        except (json.JSONDecodeError, KeyError):
            return "€ 0,00"
    

app_instance = PrintingKiosk()

@ui.page('/')
def index():
    main_container = ui.column().classes('w-full items-center')
    app_instance.render_login(main_container)


ui.run(host='0.0.0.0', port=7777, title="Printing Kiosk", show=False)