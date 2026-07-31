
import os, sys, ctypes
import tkinter as tk
from tkinter import ttk

# --- Use a UNIQUE AppUserModelID to avoid Windows taskbar grouping with Python ---
# If you still see the wrong icon, change this string to a new one and rebuild.
APP_ID = "com.fresnoops.oraclememorycalc.icon_test.v1"

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass  # Non-Windows or older builds; safe to ignore

def resource_path(rel_path: str) -> str:
    """Return absolute path to resource (works in dev & PyInstaller one-file)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Oracle Memory Calculator (Icon Test)")

        # --- Title bar / legacy icon ---
        try:
            self.iconbitmap(resource_path("./icon/OracleMemoryCalc_transparent.ico"))
        except Exception:
            pass

        # --- Some shells/Alt-Tab honor iconphoto; keep a reference to avoid GC ---
        try:
            self.icon_img = tk.PhotoImage(file=resource_path("./icon/OracleMemoryCalc_transparent.png"))
            self.iconphoto(True, self.icon_img)
        except Exception:
            pass

        frm = ttk.Frame(self, padding=24)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="If you see the green calculator/gear/RAM icon in the title bar and taskbar, it worked.").pack()

if __name__ == "__main__":
    App().mainloop()
