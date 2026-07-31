
#!/usr/bin/env python3
"""
Oracle Memory Calculator — compact Fluent-light UI,
fixed-height header strip + transparent logo (trim+scale),
header actions (Calculate + Reset) on the right,
and silky animated diff highlights (early text return).
"""

import os, sys, ctypes
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.font import Font
from oracle_mem_core import Inputs, calculate, format_report

# Optional Fluent-like ttk theme
try:
    import sv_ttk
except ImportError:
    sv_ttk = None  # app runs without it

# Pillow for trim + high-quality scale of header logo
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

APP_ID = "com.fresnoops.oraclememorycalc.gui.v21"

# ---------- Windows AppID ----------
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass

# ---------- Resource helpers ----------
def resource_path(rel_path: str) -> str:
    """Absolute path to resource (dev & PyInstaller one-file)."""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)

def _find_asset(name: str) -> str:
    for candidate in (name, os.path.join("icon", name)):
        p = resource_path(candidate)
        if os.path.exists(p):
            return p
    return resource_path(name)

# ---------- Visual constants ----------
ACCENT           = "#6FAC46"
ACCENT_HOVER     = "#66b14a"
ACCENT_PRESS     = "#5a9c3d"
SURFACE          = "#FFFFFF"   # card surface
CANVAS_BG        = "#F5F6F7"   # page gray
HEADER_STRIP_BG  = "#E6EBF0"   # header band background (slightly darker)

# Highlight colors
HILITE_INC_BG    = "#2e7d32"
HILITE_DEC_BG    = "#c62828"
HILITE_FG        = "#ffffff"   # use hex (not name) to avoid color parser issues
NEUTRAL_FG       = "#000000"   # normal report text color
EPSILON          = 1e-9

# Layout density
PAD_X = 10
PAD_Y = 2
SEP_Y = (4, 8)
OUTPUT_LINES = 24

# --------- Header sizing: decouple strip height from logo height ----------
HEADER_STRIP_HEIGHT  = 125   # px — fixed band height (does NOT grow with image)
HEADER_INNER_MARGIN  = 1     # px — top/bottom breathing room inside the strip
LOGO_TARGET_HEIGHT   = 125   # px — desired logo height (capped to fit in the strip)

# --------- Transparency/compositing toggle ----------
COMPOSITE_LOGO_ON_STRIP = False  # keep PNG transparent by default

# Defaults (used by Reset)
DEFAULTS = {
    "total": "128",
    "unit": "GiB",
    "alloc_pct": 75.0,
    "alloc_gib": "",
    "sga_pct": 83.0,
    "pga_pct": 16.0,
}

# Prefixes (must match oracle_mem_core.format_report)
PFX_ALLOC       = "Allocated to Oracle"
PFX_SGA         = "SGA_MAX / SGA_TARGET"
PFX_PGA_LIMIT   = "PGA_AGGREGATE_LIMIT"
PFX_PGA_TARGET  = "PGA_AGGREGATE_TARGET"
SQL_SGA_MAX     = "ALTER SYSTEM SET sga_max_size"
SQL_SGA_TARGET  = "ALTER SYSTEM SET sga_target"
SQL_PGA_LIMIT   = "ALTER SYSTEM SET pga_aggregate_limit"
SQL_PGA_TARGET  = "ALTER SYSTEM SET pga_aggregate_target"


class OracleMemCalcGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Oracle Memory Calculator")

        # State
        self._calc_job = None
        self._syncing = False
        self._last_changed = None
        self._fade_job = None
        self._fade_anim_jobs = []

        # Header diagnostics
        self._hdr_status = "not attempted"
        self._hdr_path = ""
        self._hdr_size = (0, 0)

        # Theme
        if sv_ttk:
            sv_ttk.set_theme("light")
        self.configure(bg=CANVAS_BG)

        # Icons & fonts
        self._setup_icons()
        self._set_fonts()

        # ttk styles
        self._style = ttk.Style(self)
        self._apply_styles()

        # Geometry
        self.geometry("900x640")
        self.resizable(True, True)

        # UI
        self._build_ui()

        # Wiring
        self._configure_highlight_tags()
        self._wire_recalc_triggers()

        # F12 diagnostics for header
        self.bind("<F12>", self._show_header_diagnostics)

        # First calculate
        self.on_calculate()

    # ---------- Icons ----------
    def _setup_icons(self):
        ico_path = _find_asset("OracleMemoryCalc_transparent.ico")
        png_path = _find_asset("OracleMemoryCalc_transparent.png")

        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass
        try:
            if os.path.exists(png_path):
                self._icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

        # WM_SETICON fallback
        try:
            WM_SETICON=0x0080; ICON_SMALL=0; ICON_BIG=1; IMAGE_ICON=1; LR_LOADFROMFILE=0x0010
            hwnd = self.winfo_id()
            LoadImageW = ctypes.windll.user32.LoadImageW
            SendMessageW = ctypes.windll.user32.SendMessageW
            if os.path.exists(ico_path):
                big = LoadImageW(None, ico_path, IMAGE_ICON, 256,256, LR_LOADFROMFILE)
                small = LoadImageW(None, ico_path, IMAGE_ICON, 16,16, LR_LOADFROMFILE)
                if big:   SendMessageW(hwnd, WM_SETICON, ICON_BIG,   big)
                if small: SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        except Exception:
            pass

    # ---------- Theme ----------
    def _set_fonts(self):
        try:
            import tkinter.font as tkfont
            for name, size in [("TkDefaultFont",10),("TkTextFont",10),("TkHeadingFont",11),
                               ("TkMenuFont",10),("TkFixedFont",10)]:
                f = tkfont.nametofont(name)
                try:
                    f.configure(family="Segoe UI Variable", size=size)
                except Exception:
                    f.configure(size=size)
        except Exception:
            pass

    def _apply_styles(self):
        self._style.configure("App.TFrame",  background=CANVAS_BG)
        self._style.configure("Card.TFrame", background=SURFACE, relief="flat", borderwidth=1)
        self._style.configure("Hint.TLabel", foreground="#666666", background=SURFACE)
        for s in ("TEntry", "TCombobox", "TSpinbox", "TLabel"):
            try: self._style.configure(s, background=SURFACE)
            except Exception: pass

    # ---------- Header helpers ----------
    def _trim_transparent(self, im):
        """Trim fully-transparent margins from an RGBA image."""
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        alpha = im.split()[-1]
        bbox = alpha.getbbox()
        return im.crop(bbox) if bbox else im

    def _to_rgb(self, color: str):
        """Return (r,g,b) from #RRGGBB/#RGB or any Tk color name."""
        if isinstance(color, str) and color.startswith("#"):
            if len(color) == 7:
                return (int(color[1:3],16), int(color[3:5],16), int(color[5:7],16))
            if len(color) == 4:
                return (int(color[1]*2,16), int(color[2]*2,16), int(color[3]*2,16))
            raise ValueError(f"Unsupported hex color: {color}")
        r16,g16,b16 = self.winfo_rgb(color)
        return (r16//256, g16//256, b16//256)

    def _load_header_image(self, target_h: int):
        """
        Load icon/header.png at requested height.
        - If Pillow: trim → scale (LANCZOS) → return transparent (no background) unless explicitly composited.
        - Else: Tk PhotoImage with integer zoom/subsample.
        Returns (PhotoImage or None, status string).
        """
        path = resource_path(os.path.join("icon", "header.png"))
        self._hdr_path = path
        if not os.path.exists(path):
            return (None, "header not found")

        if PIL_AVAILABLE:
            try:
                im = Image.open(path).convert("RGBA")
                im = self._trim_transparent(im)
                w, h = im.size
                if h != target_h:
                    scale = target_h / float(h)
                    new_w = max(1, int(round(w * scale)))
                    im = im.resize((new_w, target_h), Image.LANCZOS)
                    w, h = im.size

                if COMPOSITE_LOGO_ON_STRIP:
                    bg = Image.new("RGBA", (w, h), HEADER_STRIP_BG)
                    bg.paste(im, (0, 0), im)
                    pil_img = bg
                    status  = "composited via Pillow"
                else:
                    pil_img = im
                    status  = "transparent via Pillow"

                self._hdr_size = (w, h)
                return (ImageTk.PhotoImage(pil_img, master=self), status)
            except Exception:
                pass  # fall through to Tk path

        # Fallback: Tk PhotoImage (transparent preserved; integer scaling)
        try:
            img = tk.PhotoImage(file=path, master=self)
            h = img.height(); w = img.width()
            if h != target_h:
                if h > target_h:
                    factor = max(1, int(round(h / float(target_h))))
                    img = img.subsample(factor, factor)
                else:
                    factor = max(1, int(round(float(target_h) / h)))
                    img = img.zoom(factor, factor)
                h = img.height(); w = img.width()
            self._hdr_size = (w, h)
            return (img, "scaled via tk.PhotoImage")
        except Exception as e_tk:
            return (None, f"header fail: {e_tk!r}")

    # ---------- Layout ----------
    def _card(self, parent, pad=6):
        return ttk.Frame(parent, style="Card.TFrame", padding=pad)

    def _build_ui(self):
        # App canvas (slightly tighter padding)
        root = ttk.Frame(self, style="App.TFrame", padding=6)
        root.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header strip — FIXED HEIGHT
        header_strip = tk.Frame(
            root, bg=HEADER_STRIP_BG, bd=0, highlightthickness=0, height=HEADER_STRIP_HEIGHT
        )
        header_strip.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        header_strip.grid_columnconfigure(0, weight=1)  # col 0 (logo area) stretches
        header_strip.grid_columnconfigure(1, weight=0)  # col 1 (actions) stays compact
        header_strip.grid_propagate(False)

        # --- Left: Logo (capped to fit inside strip) ---
        max_logo_h   = max(1, HEADER_STRIP_HEIGHT - (HEADER_INNER_MARGIN * 2))
        final_logo_h = min(LOGO_TARGET_HEIGHT, max_logo_h)
        self._hdr_imgtk, self._hdr_status = self._load_header_image(final_logo_h)

        if self._hdr_imgtk:
            self._hdr_lbl = tk.Label(
                header_strip, image=self._hdr_imgtk, bg=HEADER_STRIP_BG, bd=0, highlightthickness=0
            )
            self._hdr_lbl.grid(row=0, column=0, sticky="w",
                               padx=(4, 6), pady=(HEADER_INNER_MARGIN, HEADER_INNER_MARGIN))
        else:
            self._hdr_lbl = tk.Label(
                header_strip, text="Oracle Memory Calculator", bg=HEADER_STRIP_BG, fg="#1f1f1f"
            )
            self._hdr_lbl.grid(row=0, column=0, sticky="w",
                               padx=(6, 8), pady=(HEADER_INNER_MARGIN, HEADER_INNER_MARGIN))

        # --- Right: Header actions (Calculate, Reset) ---
        actions = tk.Frame(header_strip, bg=HEADER_STRIP_BG, bd=0, highlightthickness=0)
        actions.grid(row=0, column=1, sticky="e", padx=(6, 6), pady=(HEADER_INNER_MARGIN, HEADER_INNER_MARGIN))

        # Calculate — green, compact
        self.calc_hdr_btn = tk.Button(
            actions, text="Calculate",
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOVER, activeforeground="white",
            relief=tk.FLAT, padx=12, pady=6,
            command=self.on_calculate
        )
        self.calc_hdr_btn.pack(side="left", padx=(0, 6))

        # Reset — neutral button that restores defaults
        self.reset_hdr_btn = tk.Button(
            actions, text="Reset",
            bg="#e3e3e3", fg="#111111",
            activebackground="#d6d6d6", activeforeground="#111111",
            relief=tk.FLAT, padx=10, pady=6,
            command=self.on_reset
        )
        self.reset_hdr_btn.pack(side="left")

        # Thin divider under header
        ttk.Separator(root, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=(0, 2))

        # Cards
        controls = self._card(root, pad=6)
        results  = self._card(root, pad=4)
        controls.grid(row=2, column=0, sticky="nsew")
        results.grid(row=3, column=0, sticky="nsew")

        root.rowconfigure(0, weight=0)  # header
        root.rowconfigure(1, weight=0)  # divider
        root.rowconfigure(2, weight=0)  # controls
        root.rowconfigure(3, weight=1)  # results fill
        root.columnconfigure(0, weight=1)

        # Controls grid (0=label,1=input,2=label,3=input)
        for c in (0,1,2,3):
            controls.columnconfigure(c, weight=(1 if c in (1,3) else 0))

        r = 0
        ttk.Label(controls, text="Total Memory:").grid(row=r, column=0, sticky="w", pady=(PAD_Y, PAD_Y))
        self.total_var = tk.StringVar(value=DEFAULTS["total"])
        self.total_entry = ttk.Entry(controls, textvariable=self.total_var, width=16)
        self.total_entry.grid(row=r, column=1, sticky="w", pady=(PAD_Y, PAD_Y))

        ttk.Label(controls, text="Unit:").grid(row=r, column=2, sticky="e", padx=(PAD_X, 6), pady=(PAD_Y, PAD_Y))
        self.unit_var = tk.StringVar(value=DEFAULTS["unit"])
        self.unit_cb = ttk.Combobox(controls, textvariable=self.unit_var, values=["GiB","MB"], width=8, state="readonly")
        self.unit_cb.grid(row=r, column=3, sticky="w", pady=(PAD_Y, PAD_Y))

        ttk.Separator(controls, orient="horizontal").grid(row=r+1, column=0, columnspan=4, sticky="ew", pady=SEP_Y)

        r += 2
        ttk.Label(controls, text="Allocated % of Total:").grid(row=r, column=0, sticky="w", pady=(PAD_Y, PAD_Y))
        self.alloc_pct_var = tk.DoubleVar(value=DEFAULTS["alloc_pct"])
        self.alloc_spin = ttk.Spinbox(controls, from_=0, to=100, increment=0.5, textvariable=self.alloc_pct_var, width=8)
        self.alloc_spin.grid(row=r, column=1, sticky="w", pady=(PAD_Y, PAD_Y))
        self.alloc_inline = ttk.Label(controls, text="", style="Hint.TLabel")
        self.alloc_inline.grid(row=r, column=2, columnspan=2, sticky="w", pady=(PAD_Y, PAD_Y))

        ttk.Separator(controls, orient="horizontal").grid(row=r+1, column=0, columnspan=4, sticky="ew", pady=SEP_Y)

        r += 2
        ttk.Label(controls, text="Allocated (GiB):").grid(row=r, column=0, sticky="w", pady=(PAD_Y, PAD_Y))
        self.alloc_gib_var = tk.StringVar(value=DEFAULTS["alloc_gib"])
        self.alloc_gib_entry = ttk.Entry(controls, textvariable=self.alloc_gib_var, width=16)
        self.alloc_gib_entry.grid(row=r, column=1, sticky="w", pady=(PAD_Y, PAD_Y))
        self.alloc_gib_inline = ttk.Label(controls, text="", style="Hint.TLabel")
        self.alloc_gib_inline.grid(row=r, column=2, columnspan=2, sticky="w", pady=(PAD_Y, PAD_Y))

        ttk.Separator(controls, orient="horizontal").grid(row=r+1, column=0, columnspan=4, sticky="ew", pady=SEP_Y)

        r += 2
        ttk.Label(controls, text="SGA % of Allocated:").grid(row=r, column=0, sticky="w", pady=(PAD_Y, PAD_Y))
        self.sga_var = tk.DoubleVar(value=DEFAULTS["sga_pct"])
        self.sga_spin = ttk.Spinbox(controls, from_=1, to=100, increment=0.5, textvariable=self.sga_var, width=8)
        self.sga_spin.grid(row=r, column=1, sticky="w", pady=(PAD_Y, PAD_Y))

        ttk.Separator(controls, orient="horizontal").grid(row=r+1, column=0, columnspan=4, sticky="ew", pady=SEP_Y)

        r += 2
        ttk.Label(controls, text="PGA Limit % of Allocated:").grid(row=r, column=0, sticky="w", pady=(PAD_Y, PAD_Y))
        self.pga_var = tk.DoubleVar(value=DEFAULTS["pga_pct"])
        self.pga_spin = ttk.Spinbox(controls, from_=1, to=100, increment=0.5, textvariable=self.pga_var, width=8)
        self.pga_spin.grid(row=r, column=1, sticky="w", pady=(PAD_Y, PAD_Y))

        # Results card
        results = ttk.Frame(root, style="Card.TFrame", padding=4)
        results.grid(row=3, column=0, sticky="nsew")

        self.output = tk.Text(results, height=OUTPUT_LINES, wrap="none", bd=0, highlightthickness=0,
                              background=SURFACE, relief="flat")
        mono = Font(family="Consolas", size=10)
        self.output.configure(font=mono)
        self.output.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=6, pady=6)

        yscroll = ttk.Scrollbar(results, orient="vertical", command=self.output.yview)
        yscroll.grid(row=0, column=5, sticky="ns", pady=6)
        self.output.configure(yscrollcommand=yscroll.set)

        xscroll = ttk.Scrollbar(results, orient="horizontal", command=self.output.xview)
        xscroll.grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=(0, 6))
        self.output.configure(xscrollcommand=xscroll.set)

        results.rowconfigure(0, weight=1)
        for c in range(0,5):
            results.columnconfigure(c, weight=1)

    # ---------- Header diagnostics ----------
    def _show_header_diagnostics(self, event=None):
        exists = os.path.exists(self._hdr_path) if self._hdr_path else False
        w, h = self._hdr_size
        msg = (
            "Header diagnostics\n\n"
            f"Resolved path: {self._hdr_path or '(n/a)'}\n"
            f"File exists:   {exists}\n"
            f"Load status:   {self._hdr_status}\n"
            f"Rendered size: {w} × {h} px\n"
            f"Pillow avail:  {PIL_AVAILABLE}\n"
            f"Strip height:  {HEADER_STRIP_HEIGHT}px (fixed)\n"
            f"Logo target:   {LOGO_TARGET_HEIGHT}px (capped to fit)\n"
            f"Composite?:    {COMPOSITE_LOGO_ON_STRIP}\n"
        )
        messagebox.showinfo("Header", msg, parent=self)

    # ---------- Parse / sync ----------
    def _parse_float(self, s: str):
        try: return float(s)
        except Exception: return None

    def _get_total_gib_from_fields(self):
        txt = (self.total_var.get() or "").strip()
        v = self._parse_float(txt)
        if v is None or v <= 0: return None
        return v if self.unit_var.get() == "GiB" else (v / 1024.0)

    def _sync_from_percent(self):
        if self._syncing: return
        total_gib = self._get_total_gib_from_fields()
        if total_gib is None: return
        pct = float(self.alloc_pct_var.get())
        pct = max(0.0, min(100.0, pct))
        alloc_gib = total_gib * (pct/100.0)
        self._syncing = True
        try:
            self.alloc_gib_var.set(f"{alloc_gib:.2f}")
            self.alloc_gib_inline.config(text=f"\u2248 {pct:,.1f}% of {self._format_gib(total_gib)}")
        finally:
            self._syncing = False

    def _sync_from_gib(self):
        if self._syncing: return
        total_gib = self._get_total_gib_from_fields()
        txt = (self.alloc_gib_var.get() or "").strip()
        alloc_gib = self._parse_float(txt)
        if alloc_gib is None or alloc_gib < 0: return
        if total_gib is not None and alloc_gib > total_gib:
            alloc_gib = total_gib
            self._syncing = True
            try: self.alloc_gib_var.set(f"{alloc_gib:.2f}")
            finally: self._syncing = False
        if total_gib:
            pct = (alloc_gib/total_gib*100.0) if total_gib>0 else 0.0
            pct = max(0.0, min(100.0, pct))
            self._syncing = True
            try:
                self.alloc_pct_var.set(round(pct, 2))
                self.alloc_gib_inline.config(text=f"\u2248 {pct:,.1f}% of {self._format_gib(total_gib)}")
            finally:
                self._syncing = False

    def _recalculate_debounced(self, delay_ms=25):
        if self._calc_job:
            try: self.after_cancel(self._calc_job)
            except Exception: pass
        self._calc_job = self.after(delay_ms, self.on_calculate)

    # ---------- Wiring ----------
    def _recalculate(self, event=None): self.on_calculate()

    def _on_alloc_pct_spin(self):
        self._last_changed = "alloc_percent"
        self._sync_from_percent()
        self._recalculate_debounced()

    def _on_alloc_gib_commit(self, event=None):
        self._last_changed = "alloc_gib"
        self._sync_from_gib()
        self._recalculate_debounced()

    def _on_total_changed(self, event=None):
        if self._last_changed == "alloc_gib":
            self._sync_from_gib()
        else:
            self._sync_from_percent()
        self._recalculate_debounced()

    def _wire_recalc_triggers(self):
        def mark_last(name):
            def _m(*_): self._last_changed = name
            return _m

        self.total_var.trace_add("write", mark_last("total"))
        self.unit_var.trace_add("write",  mark_last("unit"))
        self.alloc_pct_var.trace_add("write", mark_last("alloc_percent"))
        self.alloc_gib_var.trace_add("write", mark_last("alloc_gib"))
        self.sga_var.trace_add("write",   mark_last("sga"))
        self.pga_var.trace_add("write",   mark_last("pga"))

        targets = [self.total_entry, self.alloc_spin, self.alloc_gib_entry,
                   self.sga_spin, self.pga_spin, self.unit_cb]
        for w in targets:
            w.bind("<Return>", self._recalculate)
            w.bind("<KP_Enter>", self._recalculate)

        self.unit_cb.bind("<<ComboboxSelected>>", self._on_total_changed)
        self.total_entry.bind("<FocusOut>", self._on_total_changed)
        self.alloc_spin.config(command=self._on_alloc_pct_spin)
        self.sga_spin.config(command=self._recalculate)
        self.pga_spin.config(command=self._recalculate)
        self.alloc_gib_entry.bind("<FocusOut>", self._on_alloc_gib_commit)

    # ---------- Highlighting (silky fade + early text return) ----------
    def _configure_highlight_tags(self):
        self.output.tag_configure("inc", background=HILITE_INC_BG, foreground=HILITE_FG)
        self.output.tag_configure("dec", background=HILITE_DEC_BG, foreground=HILITE_FG)

    def _clear_highlights(self):
        self.output.tag_remove("inc", "1.0", "end")
        self.output.tag_remove("dec", "1.0", "end")

    def _cancel_fade_animation(self):
        for job in getattr(self, "_fade_anim_jobs", []):
            try: self.after_cancel(job)
            except Exception: pass
        self._fade_anim_jobs = []
        if getattr(self, "_fade_job", None):
            try: self.after_cancel(self._fade_job)
            except Exception: pass
            self._fade_job = None

    @staticmethod
    def _blend_rgb_linear(c_from, c_to, t):
        r = int(c_from[0] + (c_to[0] - c_from[0]) * t)
        g = int(c_from[1] + (c_to[1] - c_from[1]) * t)
        b = int(c_from[2] + (c_to[2] - c_from[2]) * t)
        return (r, g, b)

    @staticmethod
    def _blend_rgb_gamma(c_from, c_to, t, gamma=2.2):
        def to_lin(u):   return (u/255.0) ** gamma
        def to_srgb(u):  return int(round(max(0.0, min(1.0, u)) ** (1.0/gamma) * 255))
        rf = to_lin(c_from[0]); gf = to_lin(c_from[1]); bf = to_lin(c_from[2])
        rt = to_lin(c_to[0]);   gt = to_lin(c_to[1]);   bt = to_lin(c_to[2])
        r = to_srgb(rf + (rt - rf) * t)
        g = to_srgb(gf + (gt - gf) * t)
        b = to_srgb(bf + (bt - bf) * t)
        return (r, g, b)

    @staticmethod
    def _rgb_to_hex(c):
        return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"

    def _ease_out_cubic(self, x: float) -> float:
        u = 1.0 - x
        return 1.0 - (u*u*u)

    def _start_fade_animation(self, total_ms=1500, steps=28, use_gamma=True, easing="ease_out_cubic"):
        """Silky fade with early text return."""
        self._cancel_fade_animation()
        ease = (lambda x: x) if easing == "linear" else self._ease_out_cubic

        inc_src = self._to_rgb(HILITE_INC_BG)
        dec_src = self._to_rgb(HILITE_DEC_BG)
        dst_bg  = self._to_rgb(SURFACE)

        fg_src  = self._to_rgb(HILITE_FG)
        fg_dst  = self._to_rgb(NEUTRAL_FG)

        blend_fn = self._blend_rgb_gamma if use_gamma else self._blend_rgb_linear
        frame_ms = max(8, total_ms // max(1, steps))
        early_clear_index = max(1, int(steps * 0.9))  # ~90%

        def make_frame(i):
            def _frame():
                raw_t = min(1.0, max(0.0, i / float(steps)))
                t     = ease(raw_t)

                inc_c  = blend_fn(inc_src, dst_bg, t)
                dec_c  = blend_fn(dec_src, dst_bg, t)
                fg_c   = blend_fn(fg_src, fg_dst, t)

                inc_hex = self._rgb_to_hex(inc_c)
                dec_hex = self._rgb_to_hex(dec_c)
                fg_hex  = self._rgb_to_hex(fg_c)

                state = str(self.output["state"])
                try:
                    self.output.configure(state=tk.NORMAL)
                    self.output.tag_configure("inc", background=inc_hex, foreground=fg_hex)
                    self.output.tag_configure("dec", background=dec_hex, foreground=fg_hex)
                finally:
                    self.output.configure(state=state)

                if i == early_clear_index:
                    st = str(self.output["state"])
                    try:
                        self.output.configure(state=tk.NORMAL)
                        self._clear_highlights()
                    finally:
                        self.output.configure(state=st)
            return _frame

        for i in range(1, steps + 1):
            self._fade_anim_jobs.append(self.after(i * frame_ms, make_frame(i)))

        def _final_clear():
            state = str(self.output["state"])
            try:
                self.output.configure(state=tk.NORMAL)
                self._clear_highlights()
            finally:
                self.output.configure(state=state)
            self._fade_anim_jobs = []
            self._fade_job = None

        self._fade_job = self.after(total_ms + 30, _final_clear)

    def _line_highlight(self, prefix: str, tag: str):
        start = self.output.search(prefix, "1.0", stopindex="end")
        if not start: return
        self.output.tag_add(tag, f"{start} linestart", f"{start} lineend")

    def _highlight_changes(self, prev, curr):
        self._cancel_fade_animation()
        self._clear_highlights()
        self._configure_highlight_tags()

        def cmp(a, b):
            if abs(a - b) <= EPSILON: return 0
            return 1 if b > a else -1

        hr_checks = [
            (PFX_ALLOC, prev.allocated_gib,  curr.allocated_gib),
            (PFX_SGA,   float(prev.sga_gib_rounded), float(curr.sga_gib_rounded)),
            (PFX_PGA_LIMIT,  prev.pga_limit_gib,  curr.pga_limit_gib),
            (PFX_PGA_TARGET, prev.pga_target_gib, curr.pga_target_gib),
        ]
        sql_checks = [
            (SQL_SGA_MAX,    float(prev.sga_mb),       float(curr.sga_mb)),
            (SQL_SGA_TARGET, float(prev.sga_mb),       float(curr.sga_mb)),
            (SQL_PGA_LIMIT,  float(prev.pga_limit_mb), float(curr.pga_limit_mb)),
            (SQL_PGA_TARGET, float(prev.pga_target_mb),float(curr.pga_target_mb)),
        ]

        changed = False
        for prefix, pv, cv in hr_checks + sql_checks:
            d = cmp(pv, cv)
            if d > 0: self._line_highlight(prefix, "inc"); changed = True
            elif d < 0: self._line_highlight(prefix, "dec"); changed = True

        self._start_fade_animation(total_ms=1500, steps=28, use_gamma=True, easing="ease_out_cubic")

    # ---------- Inline hints ----------
    def _format_gib(self, v: float) -> str:
        return f"{v:,.2f} GiB"

    def _update_inline_status(self, inputs, results):
        try:
            self.alloc_inline.config(
                text=f"of {self._format_gib(results.total_gib)}  \u2192  {self._format_gib(results.allocated_gib)}"
            )
        except Exception: pass

        total_gib = self._get_total_gib_from_fields()
        derived_text = ""
        if total_gib is not None:
            try:
                v = float((self.alloc_gib_var.get() or "").strip())
                if v >= 0:
                    pct = (v/total_gib*100.0) if total_gib>0 else 0.0
                    derived_text = f"\u2248 {pct:,.1f}% of {self._format_gib(total_gib)}"
            except Exception:
                pass
        try:
            self.alloc_gib_inline.config(text=derived_text)
        except Exception: pass

    # ---------- Core actions ----------
    def _gather_inputs(self) -> Inputs | None:
        txt = (self.total_var.get() or "").strip()
        try:
            total_val = float(txt)
        except Exception:
            messagebox.showwarning("Input Error", "Enter a numeric 'Total Memory'."); return None
        if total_val <= 0:
            messagebox.showwarning("Input Error", "Total Memory must be > 0."); return None
        unit = self.unit_var.get()
        total_gib = total_val if unit == "GiB" else (total_val/1024.0)

        alloc_txt = (self.alloc_gib_var.get() or "").strip()
        alloc_gib_val = None
        try:
            alloc_gib_val = float(alloc_txt) if alloc_txt else None
        except Exception:
            pass

        if self._last_changed == "alloc_gib" and alloc_gib_val is not None:
            if alloc_gib_val > total_gib:
                alloc_gib_val = total_gib
                self._syncing = True
                try: self.alloc_gib_var.set(f"{alloc_gib_val:.2f}")
                finally: self._syncing = False
            pct = (alloc_gib_val/total_gib*100.0) if total_gib>0 else 0.0
            pct = max(0.0, min(100.0, pct))
            self._syncing = True
            try: self.alloc_pct_var.set(round(pct, 2))
            finally: self._syncing = False
            allocated_percent = pct/100.0
        else:
            try:
                pct = float(self.alloc_pct_var.get())
            except Exception:
                messagebox.showwarning("Input Error", "Percentages must be numeric."); return None
            if not (0.0 <= pct <= 100.0):
                messagebox.showwarning("Input Error", "Allocated % must be in [0,100]."); return None
            allocated_percent = pct/100.0
            self._sync_from_percent()

        try:
            sga_pct = float(self.sga_var.get()); pga_pct = float(self.pga_var.get())
        except Exception:
            messagebox.showwarning("Input Error", "Percentages must be numeric."); return None
        for name, v in (("SGA %", sga_pct), ("PGA Limit %", pga_pct)):
            if not (0.0 < v <= 100.0):
                messagebox.showwarning("Input Error", f"{name} must be in (0,100]."); return None

        return Inputs(
            total_value=total_val,
            total_unit=unit,
            allocated_percent=allocated_percent,
            sga_percent=sga_pct/100.0,
            pga_limit_percent=pga_pct/100.0,
        )

    def on_calculate(self):
        inputs = self._gather_inputs()
        if not inputs: return

        prev_results = getattr(self, "last_results", None)
        try:
            results = calculate(inputs)
        except Exception as e:
            messagebox.showerror("Calculation Error", str(e)); return

        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, format_report(inputs, results))
        self.output.configure(state=tk.DISABLED)

        if prev_results is not None:
            self.output.configure(state=tk.NORMAL)
            self._highlight_changes(prev_results, results)
            self.output.configure(state=tk.DISABLED)
        else:
            self._cancel_fade_animation()
            self._start_fade_animation(total_ms=900, steps=18, use_gamma=True, easing="ease_out_cubic")

        self.last_results = results
        self.last_inputs  = inputs
        self._update_inline_status(inputs, results)

    # ---------- Reset ----------
    def on_reset(self):
        """Restore all inputs and the UI to default values, then recalc."""
        # Clear any pending animations
        self._cancel_fade_animation()
        # Reset inputs
        self.total_var.set(DEFAULTS["total"])
        self.unit_var.set(DEFAULTS["unit"])
        self.alloc_pct_var.set(DEFAULTS["alloc_pct"])
        self.alloc_gib_var.set(DEFAULTS["alloc_gib"])
        self.sga_var.set(DEFAULTS["sga_pct"])
        self.pga_var.set(DEFAULTS["pga_pct"])
        # Reset focus/last-changed state
        self._last_changed = None
        # Clear output then recalc
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.configure(state=tk.DISABLED)
        self.on_calculate()


def main():
    app = OracleMemCalcGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
