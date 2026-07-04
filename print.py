import os
import sys
import threading
import tkinter as tk
from io import BytesIO
from tkinter import messagebox, ttk
import subprocess
try:
    import sv_ttk
except Exception:
    sv_ttk = None
import fitz
from PIL import Image, ImageTk

UNI_PRINTER = "Microsoft Print to PDF"
COST = 0

# Pricing table (EUR)
PRICES = {
    "bw": {"A4": 0.15, "A3": 0.20, "duplex_price": {"A4": 0.20, "A3": 0.30}},
    "color": {"A4": 0.50, "A3": 1.30, "duplex_price": {"A4": 0.75, "A3": 1.95}},
    "card": {"A4_bw": 0.50, "A3_bw": 0.80, "A4_color": 1.00, "A3_color": 2.00},
    "lamination": {"A4": 1.00, "A3": 1.60},
    "scan": {"first": 1.00, "next": 0.05}
}

def print_with_sumatra(file_path, printer_name, print_settings=""):
   
    sumatra_path = r"SumatraPDF.exe"
    
    if not os.path.exists(sumatra_path):
        raise FileNotFoundError(f"SumatraPDF non trovato in: {sumatra_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File PDF non trovato: {file_path}")

    cmd = [
        sumatra_path,
        "-print-to",
        printer_name,
        "-silent",
        "-print-settings",
        print_settings,
        file_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Errore stampa: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False
    

class PDFPrintApp:
    def __init__(self, root, pdf_path=None):
        self.root = root
        self.root.title("PDF Print Studio")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda event: self.root.destroy())

        if sv_ttk is not None:
            sv_ttk.set_theme("light")

        self.pdf_path = None
        self.doc = None
        self.file_var = tk.StringVar(value="Nessun file")
        self.print_btn = None
        self.is_printing = False
        self.print_status_var = tk.StringVar(value="")

        # cost display
        self.cost_var = tk.StringVar(value="€ 0.00")

        self.build_ui()

        if pdf_path:
            self.load_pdf(pdf_path)
        else:
            default_pdf = os.path.join(os.path.dirname(__file__), "test.pdf")
            if os.path.exists(default_pdf):
                self.load_pdf(default_pdf)

    def load_pdf(self, path):
        if not path or not os.path.exists(path):
            return

        self.pdf_path = path
        self.file_var.set(os.path.basename(path))
        if self.print_btn is not None:
            self.print_btn.config(state="normal")
        self.render_preview()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(main, text="Configurazione", padding=15, width=380)
        controls.pack(side="left", fill="y", padx=(0, 20), ipadx=15)

        ttk.Label(controls, textvariable=self.file_var, wraplength=220, justify="left").pack(fill="x", pady=(0, 8))

        ttk.Label(controls, text="Numero di copie:").pack(anchor="w", pady=(8, 0))
        self.copies_var = tk.IntVar(value=1)
        self.copies_spin = ttk.Spinbox(controls, from_=1, to=99, textvariable=self.copies_var)
        self.copies_spin.pack(fill="x", pady=5)
        self.copies_var.trace_add('write', lambda *a: self.update_cost())

        ttk.Label(controls, text="Modalità colore:").pack(anchor="w", pady=(8, 0))
        self.mode_var = tk.StringVar(value="Colore")
        self.mode_combo = ttk.Combobox(
            controls,
            textvariable=self.mode_var,
            values=["Colore", "Bianco e Nero"],
            state="readonly",
        )
        self.mode_combo.pack(fill="x", pady=5)
        self.mode_combo.bind('<<ComboboxSelected>>', lambda e: (self.update_cost(), self.render_preview()))

        # cartoncino checkbox
        self.cardstock_var = tk.BooleanVar(value=False)
        self.cardstock_chk = ttk.Checkbutton(controls, text="Stampa su cartoncino", variable=self.cardstock_var, command=self.update_cost)
        self.cardstock_chk.pack(anchor="w", pady=(6, 0))

        ttk.Label(controls, text="Pagine da stampare:").pack(anchor="w", pady=(8, 0))
        ttk.Label(controls, text="Esempio: Tutte, 1-3, 5, 7", foreground="#666666").pack(anchor="w")
        self.pages_var = tk.StringVar(value="Tutte")
        self.pages_entry = ttk.Entry(controls, textvariable=self.pages_var)
        self.pages_entry.pack(fill="x", pady=5)
        self.pages_entry.bind('<KeyRelease>', lambda e: (self.update_cost(), self.render_preview()))

        # plastificazione
        self.plast_var = tk.BooleanVar(value=False)
        self.plast_chk = ttk.Checkbutton(controls, text="Plastificazione (A4/A3)", variable=self.plast_var, command=self.update_cost)
        self.plast_chk.pack(anchor="w", pady=(6, 0))

        ttk.Label(controls, text="Formato:").pack(anchor="w", pady=(8, 0))
        self.format_var = tk.StringVar(value="A4")
        self.format_combo = ttk.Combobox(controls, textvariable=self.format_var, values=["A5", "A4", "A3"], state="readonly")
        self.format_combo.pack(fill="x", pady=5)
        self.format_combo.bind('<<ComboboxSelected>>', lambda e: self.update_cost())

        ttk.Label(controls, text="Layout:").pack(anchor="w", pady=(8, 0))
        self.layout_var = tk.StringVar(value="Uno per foglio")
        self.layout_combo = ttk.Combobox(controls, textvariable=self.layout_var, values=["Uno per foglio", "Due per foglio", "Quattro per foglio"], state="readonly")
        self.layout_combo.pack(fill="x", pady=5)
        self.layout_combo.bind('<<ComboboxSelected>>', lambda e: (self.update_cost(), self.render_preview()))

        ttk.Label(controls, text="Fronte retro:").pack(anchor="w", pady=(8, 0))
        self.fr_var = tk.StringVar(value="Solo Fronte")
        self.fr_combo = ttk.Combobox(controls, textvariable=self.fr_var, values=["Solo Fronte", "Fronte-Retro"], state="readonly")
        self.fr_combo.pack(fill="x", pady=5)
        self.fr_combo.bind('<<ComboboxSelected>>', lambda e: (self.update_cost(), self.render_preview()))

        self.print_btn = ttk.Button(controls, text="Stampa Ora", command=self.print_pdf, style="Accent.TButton")
        self.print_btn.pack(fill="x", pady=20)
        self.print_btn.config(state="disabled")

        self.status_label = ttk.Label(controls, textvariable=self.print_status_var, foreground="#333333")
        self.status_label.pack(fill="x", pady=(0, 6))
        self.print_progress = ttk.Progressbar(controls, mode="indeterminate")
        self.print_progress.pack(fill="x", pady=(0, 10))
        self.print_progress.stop()

        self.del_btn = ttk.Button(controls, text="Annulla", command=self.on_deletion, style="Accent.TButton")
        self.del_btn.pack(fill="x", pady=20)
        self.del_btn.config(state="enabled")

        # Cost label (updates live)
        ttk.Label(controls, textvariable=self.cost_var, font=("Segoe UI", 28, "bold")).pack(side="bottom", anchor="w", padx=10, pady=10)

        preview_frame = ttk.LabelFrame(main, text="Anteprima", padding=10)
        preview_frame.pack(side="right", fill="both", expand=True)

        self.canvas = tk.Canvas(preview_frame, highlightthickness=0)
        self.scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(width=1200)

        self.preview_container = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.preview_container, anchor="nw")
        self.preview_container.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        # mousewheel scrolling when cursor is over canvas
        def _on_mousewheel(event):
            if os.name == 'nt':
                delta = -1 * (event.delta // 120)
                self.canvas.yview_scroll(delta, 'units')

        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all('<MouseWheel>', _on_mousewheel))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all('<MouseWheel>'))

    def render_preview(self):
        for widget in self.preview_container.winfo_children():
            widget.destroy()

        if not self.pdf_path or not os.path.exists(self.pdf_path):
            return

        self.doc = fitz.open(self.pdf_path)
        layout_val = self.layout_var.get()
        layout_two = (layout_val == "Due per foglio")
        layout_four = (layout_val == "Quattro per foglio")
        is_bw = (self.mode_var.get() == "Bianco e Nero")

        try:
            selected_pages = self.parse_page_selection(len(self.doc))
        except Exception:
            selected_pages = None

        if selected_pages is None:
            pages = [p for p in self.doc]
            page_numbers = list(range(1, len(self.doc) + 1))
        else:
            pages = [self.doc[i - 1] for i in selected_pages]
            page_numbers = selected_pages

        if not layout_two and not layout_four:
            for index, page in enumerate(pages):
                if is_bw:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csGRAY)
                    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    img = img.convert("RGB")
                else:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                img.thumbnail((650, 900))
                photo = ImageTk.PhotoImage(img)

                frame = ttk.Frame(self.preview_container)
                frame.pack(pady=5, fill="x")

                label = ttk.Label(frame, image=photo)
                label.image = photo
                label.pack()

                page_num = page_numbers[index]
                ttk.Label(frame, text=f"Pagina {page_num}", foreground="#666666").pack(pady=(4, 0))
        elif layout_two:
            # two-up: combine pages in pairs side-by-side
            total = len(pages)
            pair_index = 0
            while pair_index < total:
                p1 = pages[pair_index]
                p2 = pages[pair_index + 1] if (pair_index + 1) < total else None

                if is_bw:
                    pix1 = p1.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), colorspace=fitz.csGRAY)
                    img1 = Image.frombytes("L", (pix1.width, pix1.height), pix1.samples).convert("RGB")
                    if p2:
                        pix2 = p2.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), colorspace=fitz.csGRAY)
                        img2 = Image.frombytes("L", (pix2.width, pix2.height), pix2.samples).convert("RGB")
                    else:
                        img2 = None
                else:
                    pix1 = p1.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    img1 = Image.frombytes("RGB", (pix1.width, pix1.height), pix1.samples)
                    if p2:
                        pix2 = p2.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                        img2 = Image.frombytes("RGB", (pix2.width, pix2.height), pix2.samples)
                    else:
                        img2 = None

                # normalize heights
                h = max(img1.height, img2.height if img2 else 0)
                w = img1.width + (img2.width if img2 else 0)
                combined = Image.new("RGB", (w, h), (255, 255, 255))
                combined.paste(img1, (0, 0))
                if img2:
                    combined.paste(img2, (img1.width, 0))

                combined.thumbnail((1100, 800))
                photo = ImageTk.PhotoImage(combined)

                frame = ttk.Frame(self.preview_container)
                frame.pack(pady=5, fill="x")

                label = ttk.Label(frame, image=photo)
                label.image = photo
                label.pack()

                left_idx = page_numbers[pair_index]
                right_idx = page_numbers[pair_index + 1] if (pair_index + 1) < total else ''
                ttk.Label(frame, text=f"Pagine {left_idx}{('-' + str(right_idx)) if right_idx else ''} (due per foglio)", foreground="#666666").pack(pady=(4, 0))

                pair_index += 2
        else:
            # four-up: combine pages in 2x2 grid
            total = len(pages)
            idx = 0
            while idx < total:
                group = []
                for j in range(4):
                    if idx + j < total:
                        group.append(pages[idx + j])
                    else:
                        group.append(None)

                imgs = []
                for pg in group:
                    if pg is None:
                        imgs.append(None)
                        continue
                    if is_bw:
                        pix = pg.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), colorspace=fitz.csGRAY)
                        im = Image.frombytes("L", (pix.width, pix.height), pix.samples).convert("RGB")
                    else:
                        pix = pg.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    imgs.append(im)

                # normalize tile size
                tile_w = max((im.width for im in imgs if im), default=0)
                tile_h = max((im.height for im in imgs if im), default=0)
                if tile_w == 0 or tile_h == 0:
                    break

                # create grid 2x2
                combined_w = tile_w * 2
                combined_h = tile_h * 2
                combined = Image.new("RGB", (combined_w, combined_h), (255, 255, 255))
                positions = [(0, 0), (tile_w, 0), (0, tile_h), (tile_w, tile_h)]
                for k, im in enumerate(imgs):
                    if im:
                        im_resized = im.resize((tile_w, tile_h), Image.LANCZOS)
                        combined.paste(im_resized, positions[k])

                combined.thumbnail((1200, 1000))
                photo = ImageTk.PhotoImage(combined)

                frame = ttk.Frame(self.preview_container)
                frame.pack(pady=5, fill="x")
                label = ttk.Label(frame, image=photo)
                label.image = photo
                label.pack()

                selected_group = page_numbers[idx:idx+4]
                label_range = f"{selected_group[0]}-{selected_group[-1]}" if len(selected_group) > 1 else str(selected_group[0])
                ttk.Label(frame, text=f"Pagine {label_range} (quattro per foglio)", foreground="#666666").pack(pady=(4, 0))

                idx += 4

        self.preview_container.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Update cost when preview (and page count) changes
        self.update_cost()

    def parse_page_selection(self, total_pages):
        value = self.pages_var.get().strip()
        if not value or value.lower() in {"tutte", "all"}:
            return None

        selected = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    start_text, end_text = part.split("-", 1)
                    start = int(start_text.strip())
                    end = int(end_text.strip())
                except ValueError as exc:
                    raise ValueError("Formato pagine non valido. Usa esempi come 1-3, 5, 7") from exc
                if start > end:
                    start, end = end, start
            else:
                start = end = int(part)

            if not 1 <= start <= total_pages or not 1 <= end <= total_pages:
                raise ValueError(f"Le pagine devono essere tra 1 e {total_pages}")

            selected.extend(range(start, end + 1))

        return sorted(set(selected))

    def prepare_print_pdf(self):
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            raise FileNotFoundError("Nessun PDF selezionato")

        selected_pages = self.parse_page_selection(len(fitz.open(self.pdf_path)))
        if selected_pages is None:
            selected_pages = list(range(1, len(fitz.open(self.pdf_path)) + 1))

        input_doc = fitz.open(self.pdf_path)
        output_doc = fitz.open()
        local_tmp_dir = os.path.join(os.path.dirname(__file__), "tmp")
        os.makedirs(local_tmp_dir, exist_ok=True)
        try:
            layout_val = self.layout_var.get()
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
                        im_resized = im.resize((tile_w, tile_h), Image.LANCZOS)
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
                    output_doc.insert_pdf(input_doc, from_page=page_num - 1, to_page=page_num - 1)

            output_path = os.path.join(local_tmp_dir, f"selected_pages_{os.path.basename(self.pdf_path)}")
            output_doc.save(output_path)
            return output_path
        finally:
            input_doc.close()
            output_doc.close()

    def compute_cost(self):
        # Determine page count
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            return 0.0
        with fitz.open(self.pdf_path) as d:
            total_pages = len(d)

        selected = self.parse_page_selection(total_pages)
        if selected is None:
            pages_to_print = total_pages
        else:
            pages_to_print = len(selected)

        copies = max(1, int(self.copies_var.get() or 1))

        # Determine base price unit
        size = self.format_var.get() or "A4"
        is_color = (self.mode_var.get() == "Colore")
        is_card = bool(self.cardstock_var.get())
        is_duplex = (self.fr_var.get() == "Fronte-Retro")
        layout_two = (self.layout_var.get() == "Due per foglio")

        # pages per physical sheet (for preview/layout)
        layout_four = (self.layout_var.get() == "Quattro per foglio")
        pages_per_sheet = 2 if layout_two else 4 if layout_four else 1
        if is_duplex:
            pages_per_sheet *= 2
        sheets_per_copy = (pages_to_print + pages_per_sheet - 1) // pages_per_sheet

        # determine unit price (page and duplex prices)
        if is_card:
            key = f"{size}_color" if is_color else f"{size}_bw"
            if key == "A4_color":
                page_price = PRICES["card"]["A4_color"]
            elif key == "A3_color":
                page_price = PRICES["card"].get("A3_color", PRICES["card"]["A4_color"])
            elif key == "A4_bw":
                page_price = PRICES["card"]["A4_bw"]
            else:
                page_price = PRICES["card"].get("A3_bw", PRICES["card"]["A4_bw"])
            duplex_price = page_price
        else:
            if is_color:
                page_price = PRICES["color"].get(size, PRICES["color"]["A4"])
                duplex_price = PRICES["color"].get("duplex_price", {}).get(size, page_price)
            else:
                page_price = PRICES["bw"].get(size, PRICES["bw"]["A4"])
                duplex_price = PRICES["bw"].get("duplex_price", {}).get(size, page_price)

        if is_duplex:
            duplex_sheets = pages_to_print // pages_per_sheet
            leftover_pages = pages_to_print % pages_per_sheet
            base_cost = (duplex_sheets * duplex_price + leftover_pages * page_price) * copies
        elif layout_two or layout_four:
            base_cost = page_price * sheets_per_copy * copies
        else:
            base_cost = page_price * pages_to_print * copies

        # plastificazione cost per sheet if requested
        plast_cost = 0.0
        if self.plast_var.get():
            lam_price = PRICES["lamination"].get(size, PRICES["lamination"]["A4"])
            sheets = (pages_to_print + (2 if self.layout_var.get() == "Due per foglio" else 4 if self.layout_var.get() == "Quattro per foglio" else 1) - 1) // (2 if self.layout_var.get() == "Due per foglio" else 4 if self.layout_var.get() == "Quattro per foglio" else 1)
            plast_cost = lam_price * sheets * copies

        total = base_cost + plast_cost
        return round(total + 1e-9, 2)

    def update_cost(self, *args):
        try:
            c = self.compute_cost()
            self.cost_var.set(f"€ {c:.2f}")
        except Exception:
            self.cost_var.set("€ 0.00")

    def print_settings(self):
        copies = self.copies_var.get()
        color_mode = "color" if self.mode_var.get() == "Colore" else "monochrome"
        layout = "duplex" if self.fr_var.get() == "Fronte-Retro" else "simplex"
        return f"{copies}x,{color_mode},{self.format_var.get()},{layout},ignore-pdf-print-settings"

    def print_pdf(self):
        if not self.pdf_path:
            messagebox.showwarning("Attenzione", "Seleziona un PDF")
            return
        if self.is_printing:
            return

        self.is_printing = True
        self.print_btn.config(state="disabled")
        self.print_status_var.set("Invio stampa in corso...")
        self.print_progress.start(10)

        printer = UNI_PRINTER
        settings = self.print_settings()
        threading.Thread(target=self._print_worker, args=(printer, settings), daemon=True).start()

    def _print_worker(self, printer, settings):
        try:
            print_pdf_path = self.prepare_print_pdf()
            success = print_with_sumatra(print_pdf_path, printer, settings)
            if success:
                result = ("info", "Successo", "Stampa inviata!")
            else:
                result = ("warning", "Attenzione", "La stampa non è stata inviata. Controlla SumatraPDF.")
        except ValueError as exc:
            result = ("error", "Errore", str(exc))
        except Exception as exc:
            result = ("error", "Errore", str(exc))

        self.root.after(0, lambda: self._on_print_finished(*result))

    def _on_print_finished(self, kind, title, message):
        self.is_printing = False
        self.print_progress.stop()
        self.print_status_var.set("")

        if kind == "info":
            self.print_status_var.set("Stampa completata. Chiusura in corso...")
            self.root.after(800, self.root.destroy)
        elif kind == "warning":
            self.print_btn.config(state="normal")
            messagebox.showwarning(title, message)
        else:
            self.print_btn.config(state="normal")
            messagebox.showerror(title, message)

    def on_deletion(self):
        self.root.after(800, self.root.destroy)

def main(pdf_path=None):
    root = tk.Tk()
    if sv_ttk is not None:
        sv_ttk.set_theme("light")

    if pdf_path is None and len(sys.argv) > 1:
        pdf_path = sys.argv[1]

    PDFPrintApp(root, pdf_path=pdf_path)
    root.mainloop()


if __name__ == "__main__":
    main()