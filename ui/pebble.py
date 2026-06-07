import math, queue, threading, tkinter as tk
from tkinter import scrolledtext

_COLORS = {
    "idle":      "#1E90FF",
    "listening": "#00C853",
    "thinking":  "#FFAB00",
    "speaking":  "#00BCD4",
}
_BG       = "#0d0d0d"
_PANEL    = "#141414"
_TEXT_FG  = "#e0e0e0"
_DIM_FG   = "#606060"
_ACCENT   = "#1E90FF"

_state_q: queue.Queue = queue.Queue()
_text_q:  queue.Queue = queue.Queue()


class PebbleUI:
    def __init__(self, on_text_input):
        self._cb = on_text_input
        self._root = None
        self._canvas = None
        self._log = None
        self._entry = None
        self._state_lbl = None
        self._drag_x = self._drag_y = 0
        self._orb_phase = 0.0
        self._current_state = "idle"

    def _build(self):
        root = tk.Tk()
        root.withdraw()  # hide while building — prevents invisible-window bug on Windows 11

        root.configure(bg=_BG)
        root.resizable(False, False)

        # ── title bar ──────────────────────────────────────────────────────
        bar = tk.Frame(root, bg="#0a0a0a", height=24)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        tk.Label(bar, text="  J.A.R.V.I.S", font=("Consolas", 9, "bold"),
                 fg=_ACCENT, bg="#0a0a0a").pack(side="left", pady=3)

        btn_x = tk.Label(bar, text="✕", font=("Consolas", 9),
                         fg=_DIM_FG, bg="#0a0a0a", cursor="hand2", padx=8)
        btn_x.pack(side="right")
        btn_x.bind("<Button-1>", lambda e: root.destroy())
        btn_x.bind("<Enter>", lambda e: btn_x.config(fg="#ff4444"))
        btn_x.bind("<Leave>", lambda e: btn_x.config(fg=_DIM_FG))

        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

        # ── main body ──────────────────────────────────────────────────────
        body = tk.Frame(root, bg=_BG)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Orb canvas (left column)
        orb_frame = tk.Frame(body, bg=_BG, width=72)
        orb_frame.pack(side="left", fill="y", padx=(6, 0))
        orb_frame.pack_propagate(False)

        canvas = tk.Canvas(orb_frame, width=66, height=200, bg=_BG,
                           highlightthickness=0)
        canvas.pack(pady=(10, 0))
        canvas.create_oval(6, 6, 60, 60, fill="", outline="#1E90FF",
                           width=2, tags="glow")
        canvas.create_oval(12, 12, 54, 54, fill="#1E90FF", outline="",
                           tags="orb")

        state_lbl = tk.Label(orb_frame, text="idle", font=("Consolas", 7),
                             fg=_DIM_FG, bg=_BG)
        state_lbl.pack()

        # Right column — log + input
        right = tk.Frame(body, bg=_BG)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=4)

        log = scrolledtext.ScrolledText(
            right, font=("Consolas", 9), bg=_PANEL, fg=_TEXT_FG,
            relief="flat", bd=0, wrap=tk.WORD, state="disabled",
            insertbackground=_ACCENT, height=9,
            selectbackground="#1a3a5c",
        )
        log.pack(fill="both", expand=True)
        log.tag_config("you",    foreground="#aaaaaa")
        log.tag_config("jarvis", foreground="#00e5ff")
        log.tag_config("agent",  foreground="#888800")

        # Input row
        inp_row = tk.Frame(right, bg=_BG)
        inp_row.pack(fill="x", pady=(4, 2))

        tk.Label(inp_row, text=">", font=("Consolas", 10, "bold"),
                 fg=_ACCENT, bg=_BG).pack(side="left")

        entry = tk.Entry(inp_row, font=("Consolas", 9), bg=_PANEL,
                         fg="#00e5ff", insertbackground="#00e5ff",
                         relief="flat", bd=0)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        entry.bind("<Return>", self._submit)
        entry.focus_set()

        tk.Label(inp_row, text="⏎", font=("Consolas", 8),
                 fg=_DIM_FG, bg=_BG).pack(side="right")

        self._root   = root
        self._canvas = canvas
        self._log    = log
        self._entry  = entry
        self._state_lbl = state_lbl

        # Center on screen, then show with decorations removed
        root.update_idletasks()
        sw = root.winfo_screenwidth() or 1920
        sh = root.winfo_screenheight() or 1080
        x = max(0, (sw - 420) // 2)
        y = max(0, (sh - 260) // 2)
        root.geometry(f"420x260+{x}+{y}")

        # Apply frameless style and show — order matters on Windows
        root.overrideredirect(True)
        root.attributes("-alpha", 0.95)
        root.attributes("-topmost", True)
        root.deiconify()
        root.update()
        root.lift()

        return root

    # ── drag ───────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x_root, e.y_root

    def _drag_move(self, e):
        x = self._root.winfo_x() + e.x_root - self._drag_x
        y = self._root.winfo_y() + e.y_root - self._drag_y
        self._root.geometry(f"+{x}+{y}")
        self._drag_x, self._drag_y = e.x_root, e.y_root

    # ── input ──────────────────────────────────────────────────────────────
    def _submit(self, _=None):
        text = self._entry.get().strip()
        self._entry.delete(0, tk.END)
        if text:
            self._log_append(f"You: {text}\n", "you")
            self._cb(text)

    # ── log ────────────────────────────────────────────────────────────────
    def _log_append(self, text: str, tag: str = ""):
        self._log.config(state="normal")
        self._log.insert(tk.END, text, tag)
        self._log.see(tk.END)
        self._log.config(state="disabled")

    # ── orb animation ──────────────────────────────────────────────────────
    def _animate(self):
        self._orb_phase = (self._orb_phase + 0.08) % (2 * math.pi)
        color = _COLORS.get(self._current_state, _COLORS["idle"])

        if self._current_state in ("thinking", "speaking", "listening"):
            self._canvas.itemconfig("glow", outline=color, width=3)
            r = 4 + 2 * abs(math.sin(self._orb_phase))
            self._canvas.coords("orb", 12 - r, 12 - r, 54 + r, 54 + r)
        else:
            self._canvas.itemconfig("glow", outline=color, width=1)
            self._canvas.coords("orb", 12, 12, 54, 54)

        self._canvas.itemconfig("orb", fill=color)
        self._root.after(50, self._animate)

    # ── poll queues ────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                state = _state_q.get_nowait()
                self._current_state = state
                self._state_lbl.config(text=state,
                                       fg=_COLORS.get(state, _DIM_FG))
        except queue.Empty:
            pass
        try:
            while True:
                text, tag = _text_q.get_nowait()
                self._log_append(text, tag)
        except queue.Empty:
            pass
        self._root.after(80, self._poll)

    # ── run ────────────────────────────────────────────────────────────────
    def run(self):
        self._build()
        self._root.after(80, self._poll)
        self._root.after(50, self._animate)
        self._root.mainloop()


# ── public API ─────────────────────────────────────────────────────────────

def set_state(state: str):
    _state_q.put(state)


def set_text(text: str, tag: str = "jarvis"):
    _text_q.put((text, tag))


def launch(on_text_input, daemon: bool = True):
    t = threading.Thread(target=PebbleUI(on_text_input).run,
                         daemon=daemon, name="pebble-ui")
    t.start()
    return t
