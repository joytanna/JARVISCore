"""
Futuristic full-screen AI dashboard.
Animated orb · scanning line · orbit particles · waveform · typing animation.
"""
import datetime, math, queue, tkinter as tk

# ── palette ───────────────────────────────────────────────────────────────
_BG    = "#03050e"   # deep-space black
_SIDE  = "#04060f"   # sidebar bg
_CHAT  = "#030508"   # chat panel bg
_BORD  = "#0b1d38"   # dim border
_GRID  = "#080f1e"   # hex-grid dot colour

_CYAN   = "#00e5ff"
_GREEN  = "#00ff88"
_AMBER  = "#fbbf24"
_PURPLE = "#c084fc"
_DIM    = "#112840"
_TEXT   = "#6ba3c0"
_TBRI   = "#cce8ff"
_YOU    = "#5fa8d3"
_AI     = "#d4f1ff"

_STATE  = {"idle": _CYAN, "listening": _GREEN,
           "thinking": _AMBER, "speaking": _PURPLE}

# ── queues (thread-safe cross-thread communication) ───────────────────────
_text_q:  queue.Queue = queue.Queue()
_state_q: queue.Queue = queue.Queue()


def _dim(color: str, f: float) -> str:
    """Scale #rrggbb by factor f (0–1)."""
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"


# ═══════════════════════════════════════════════════════════════════════════
class FullscreenUI:
    def __init__(self, on_input):
        self._cb          = on_input
        self._root        = None
        self._log         = None
        self._entry       = None
        self._inp_frame   = None    # pulsing neon border
        self._orb_cv      = None    # orb canvas
        self._wave_cv     = None    # waveform canvas
        self._state_lbl   = None
        self._time_lbl    = None
        self._cpu_lbl     = None
        self._cpu_bar     = None
        self._ram_bar     = None

        # animation state
        self._phase       = 0.0
        self._scan_y      = 0.0
        self._inp_pulse   = 0.0
        self._cur_state   = "idle"
        self._inp_focused = False

        # typing-animation state
        self._type_queue: list[tuple[str, str]] = []
        self._typing      = False
        self._type_buf    = ""
        self._type_tail   = ""
        self._type_pos    = 0
        self._type_tag    = ""

    # ──────────────────────────────────────────────────────────────────────
    def _build(self, root: tk.Tk):
        root.configure(bg=_BG)
        root.title("Assistant")
        root.bind("<Escape>", lambda _: self.hide())

        # ── TOP BAR ───────────────────────────────────────────────────────
        top = tk.Frame(root, bg="#020307", height=40)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        tk.Label(top, text="◈  A I  A S S I S T A N T",
                 font=("Consolas", 10, "bold"),
                 fg=_CYAN, bg="#020307").pack(side="left", padx=18, pady=10)

        close_btn = tk.Label(top, text=" ✕ ", font=("Consolas", 11),
                             fg=_DIM, bg="#020307", cursor="hand2")
        close_btn.pack(side="right", padx=10)
        close_btn.bind("<Button-1>", lambda _: self.hide())
        close_btn.bind("<Enter>",    lambda _: close_btn.config(fg="#ff4444"))
        close_btn.bind("<Leave>",    lambda _: close_btn.config(fg=_DIM))

        self._time_lbl = tk.Label(top, text="", font=("Consolas", 11),
                                  fg=_TBRI, bg="#020307")
        self._time_lbl.pack(side="right", padx=24)

        self._cpu_lbl = tk.Label(top, text="", font=("Consolas", 8),
                                 fg=_DIM, bg="#020307")
        self._cpu_lbl.pack(side="right", padx=10)

        # neon line under top bar
        tk.Frame(root, bg=_CYAN, height=1).pack(fill="x")

        # ── BODY ──────────────────────────────────────────────────────────
        body = tk.Frame(root, bg=_BG)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        tk.Frame(body, bg=_BORD, width=1).pack(side="left", fill="y")
        self._build_chat(body)

    # ── SIDEBAR ───────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        side = tk.Frame(parent, bg=_SIDE, width=230)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        # ── Orb canvas ────────────────────────────────────────────────────
        cv = tk.Canvas(side, width=230, height=230,
                       bg=_SIDE, highlightthickness=0)
        cv.pack()

        # hex-grid dots (decorative background)
        for row in range(12):
            for col in range(9):
                ox = col * 26 + (row % 2) * 13
                oy = row * 22 + 4
                cv.create_oval(ox, oy, ox + 2, oy + 2,
                               fill=_GRID, outline="", tags="hd")

        # circuit trace lines (decorative)
        for y in (40, 80, 190):
            cv.create_line(0, y, 40, y, fill=_GRID, width=1, tags="trace")
            cv.create_line(190, y, 230, y, fill=_GRID, width=1, tags="trace")

        cx, cy, r = 115, 115, 64

        # Glow rings — outer → inner  (radius, dim factor)
        for i, (ri, f) in enumerate([
            (106, 0.03), (94, 0.07), (83, 0.14),
            (73,  0.26), (63, 0.50), (53, 0.85),
        ]):
            cv.create_oval(cx - ri, cy - ri, cx + ri, cy + ri,
                           fill="", outline=_dim(_CYAN, f),
                           width=1, tags=f"ring{i}")

        # Core
        cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=_CYAN, outline="", tags="core")

        # Inner reflection / glint
        cv.create_oval(cx - 20, cy - 28, cx - 2, cy - 14,
                       fill="#ffffff", outline="", tags="glint")

        # Scanning line
        cv.create_line(cx - r, cy, cx + r, cy,
                       fill=_dim(_CYAN, 0.3), width=2, tags="scan")

        # Orbit particles (4 dots)
        for i in range(4):
            cv.create_oval(0, 0, 7, 7, fill=_CYAN, outline="",
                           tags=f"part{i}", state="hidden")

        self._orb_cv = cv
        self._cx, self._cy, self._r = cx, cy, r

        # ── State label ───────────────────────────────────────────────────
        self._state_lbl = tk.Label(side, text="◈  idle",
                                   font=("Consolas", 9, "bold"),
                                   fg=_CYAN, bg=_SIDE)
        self._state_lbl.pack(pady=(3, 1))

        # ── Waveform ──────────────────────────────────────────────────────
        wv = tk.Canvas(side, width=230, height=36,
                       bg=_SIDE, highlightthickness=0)
        wv.pack()
        for i in range(14):
            x = 28 + i * 13
            wv.create_rectangle(x, 16, x + 8, 20,
                                 fill=_DIM, outline="", tags=f"wv{i}")
        self._wave_cv = wv

        # divider
        tk.Frame(side, bg=_BORD, height=1).pack(fill="x", padx=14, pady=6)

        # ── System stats ──────────────────────────────────────────────────
        tk.Label(side, text="─── SYSTEMS ───",
                 font=("Consolas", 7), fg=_DIM, bg=_SIDE).pack(pady=2)

        self._cpu_bar = tk.Label(side, text="CPU  ░░░░░░░░░░  ─",
                                 font=("Consolas", 8), fg=_DIM,
                                 bg=_SIDE, anchor="w")
        self._cpu_bar.pack(fill="x", padx=18, pady=1)

        self._ram_bar = tk.Label(side, text="RAM  ░░░░░░░░░░  ─",
                                 font=("Consolas", 8), fg=_DIM,
                                 bg=_SIDE, anchor="w")
        self._ram_bar.pack(fill="x", padx=18, pady=1)

        tk.Frame(side, bg=_BORD, height=1).pack(fill="x", padx=14, pady=8)

        # ── Quick commands ────────────────────────────────────────────────
        tk.Label(side, text="─── COMMANDS ───",
                 font=("Consolas", 7), fg=_DIM, bg=_SIDE).pack(pady=2)
        for cmd in [
            "search [query]", "open [app]",
            "call [name]",    "remind me [time] to [x]",
            "brief me",       "read screen",
            "set volume [n]", "lock screen",
            "what's on screen", "summarize file [path]",
        ]:
            tk.Label(side, text=f"  › {cmd}",
                     font=("Consolas", 7), fg="#0e2640",
                     bg=_SIDE, anchor="w").pack(fill="x", padx=16, pady=1)

    # ── CHAT PANEL ────────────────────────────────────────────────────────
    def _build_chat(self, parent):
        chat = tk.Frame(parent, bg=_CHAT)
        chat.pack(side="left", fill="both", expand=True)

        # ── Log (tk.Text + slim scrollbar) ────────────────────────────────
        log_frame = tk.Frame(chat, bg=_CHAT)
        log_frame.pack(fill="both", expand=True)

        log = tk.Text(
            log_frame,
            font=("Consolas", 12),
            bg=_CHAT, fg=_TEXT,
            relief="flat", bd=0,
            wrap=tk.WORD,
            state="disabled",
            padx=32, pady=22,
            spacing1=1, spacing3=8,
            insertbackground=_CYAN,
            cursor="arrow",
        )
        sb = tk.Scrollbar(log_frame, orient="vertical", command=log.yview,
                          bg=_SIDE, troughcolor=_BG,
                          activebackground=_DIM,
                          width=5, relief="flat", bd=0)
        log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        log.pack(side="left", fill="both", expand=True)

        # message tags
        log.tag_config("you",     foreground=_YOU,  font=("Consolas", 12))
        log.tag_config("jarvis",  foreground=_AI,   font=("Consolas", 12))
        log.tag_config("lbl_you", foreground="#194060",
                       font=("Consolas", 8, "bold"))
        log.tag_config("lbl_ai",  foreground=_CYAN,
                       font=("Consolas", 8, "bold"))

        # ── Input bar ─────────────────────────────────────────────────────
        inp_bar = tk.Frame(chat, bg="#030610", pady=0)
        inp_bar.pack(fill="x", side="bottom")
        tk.Frame(inp_bar, bg=_CYAN, height=1).pack(fill="x")  # neon top line

        row = tk.Frame(inp_bar, bg="#030610")
        row.pack(fill="x", padx=20, pady=12)

        # Pulsing border wrapper
        inp_frame = tk.Frame(row, bg=_DIM, padx=1, pady=1)
        inp_frame.pack(side="left", fill="x", expand=True)

        entry = tk.Entry(inp_frame,
                         font=("Consolas", 12),
                         bg="#020510", fg=_CYAN,
                         insertbackground=_CYAN,
                         relief="flat", bd=0)
        entry.pack(fill="x", ipady=9, padx=6)
        entry.bind("<Return>",   self._submit)
        entry.bind("<FocusIn>",  lambda _: setattr(self, "_inp_focused", True))
        entry.bind("<FocusOut>", lambda _: setattr(self, "_inp_focused", False))

        tx_btn = tk.Label(row, text=" TRANSMIT ",
                          font=("Consolas", 9, "bold"),
                          fg=_BG, bg=_CYAN,
                          cursor="hand2", pady=9)
        tx_btn.pack(side="right", padx=(12, 0))
        tx_btn.bind("<Button-1>", self._submit)
        tx_btn.bind("<Enter>",    lambda _: tx_btn.config(bg="#00b8cc"))
        tx_btn.bind("<Leave>",    lambda _: tx_btn.config(bg=_CYAN))

        self._log       = log
        self._entry     = entry
        self._inp_frame = inp_frame

    # ──────────────────────────────────────────────────────────────────────
    # ANIMATION
    # ──────────────────────────────────────────────────────────────────────
    def _animate(self):
        self._phase  = (self._phase + 0.055) % (6.2832)
        self._scan_y = (self._scan_y + 0.017) % 1.0

        color   = _STATE.get(self._cur_state, _CYAN)
        active  = self._cur_state != "idle"
        cx, cy, r = self._cx, self._cy, self._r

        # ── glow rings ────────────────────────────────────────────────────
        ring_specs = [
            (106, 0.03), (94, 0.07), (83, 0.14),
            (73,  0.26), (63, 0.50), (53, 0.85),
        ]
        for i, (ri, base_f) in enumerate(ring_specs):
            pulse = 1.0 + 0.20 * math.sin(self._phase + i * 0.55) if active else 1.0
            c     = _dim(color, min(base_f * pulse, 1.0))
            w     = 2 if i >= 4 else 1
            self._orb_cv.itemconfig(f"ring{i}", outline=c, width=w)

        # ── core ──────────────────────────────────────────────────────────
        core_r = r + (5 * abs(math.sin(self._phase)) if active else 0)
        self._orb_cv.coords("core",
                            cx - core_r, cy - core_r,
                            cx + core_r, cy + core_r)
        self._orb_cv.itemconfig("core", fill=_dim(color, 0.88))

        # glint stays fixed relative to core
        self._orb_cv.coords("glint", cx - 22, cy - 30, cx - 4, cy - 16)

        # ── scanning line ─────────────────────────────────────────────────
        sy = cy - r + self._scan_y * 2 * r
        dh = sy - cy
        cr = math.sqrt(max(0.0, r * r - dh * dh))
        if cr > 2:
            self._orb_cv.coords("scan", cx - cr, sy, cx + cr, sy)
            self._orb_cv.itemconfig("scan", fill=_dim(color, 0.45), state="normal")
        else:
            self._orb_cv.itemconfig("scan", state="hidden")

        # ── orbit particles ────────────────────────────────────────────────
        show_p = self._cur_state in ("speaking", "listening")
        for i in range(4):
            spd   = 1.3 + i * 0.18
            angle = self._phase * spd + i * (math.pi / 2)
            pr    = r + 22 + i * 7
            px    = cx + pr * math.cos(angle)
            py    = cy + pr * math.sin(angle) * 0.65
            ps    = 3 + (i % 2)
            self._orb_cv.coords(f"part{i}", px - ps, py - ps, px + ps, py + ps)
            self._orb_cv.itemconfig(f"part{i}",
                                    fill=_dim(color, 0.75),
                                    state="normal" if show_p else "hidden")

        # ── waveform bars ─────────────────────────────────────────────────
        for i in range(14):
            hb = 2 + 13 * abs(math.sin(self._phase * 2.2 + i * 0.55)) if active else 2
            x  = 28 + i * 13
            self._wave_cv.coords(f"wv{i}", x, 18 - hb, x + 8, 18 + hb)
            self._wave_cv.itemconfig(f"wv{i}",
                                     fill=_dim(color, 0.55) if active else _DIM)

        # ── input border pulse ─────────────────────────────────────────────
        self._inp_pulse = (self._inp_pulse + 0.10) % 6.2832
        if self._inp_frame:
            if self._inp_focused:
                f = 0.45 + 0.55 * abs(math.sin(self._inp_pulse))
                self._inp_frame.config(bg=_dim(_CYAN, f))
            else:
                self._inp_frame.config(bg=_DIM)

        if self._root:
            self._root.after(50, self._animate)

    # ──────────────────────────────────────────────────────────────────────
    # CLOCK & SYSTEM STATS
    # ──────────────────────────────────────────────────────────────────────
    def _tick(self):
        now = datetime.datetime.now()
        self._time_lbl.config(text=now.strftime("%H:%M:%S   ·   %a %d %b"))

        def _bar(pct: float) -> str:
            n = int(pct / 10)
            return "▓" * n + "░" * (10 - n)

        def _bar_color(pct: float) -> str:
            return _CYAN if pct < 65 else _AMBER if pct < 85 else "#ff4444"

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self._cpu_bar.config(text=f"CPU  {_bar(cpu)}  {cpu:4.1f}%",
                                 fg=_bar_color(cpu))
            self._ram_bar.config(text=f"RAM  {_bar(ram)}  {ram:4.1f}%",
                                 fg=_bar_color(ram))
            self._cpu_lbl.config(text=f"CPU {cpu:.0f}%  RAM {ram:.0f}%")
        except ImportError:
            pass

        if self._root:
            self._root.after(2000, self._tick)

    # ──────────────────────────────────────────────────────────────────────
    # QUEUE POLLING
    # ──────────────────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                state = _state_q.get_nowait()
                self._cur_state = state
                color = _STATE.get(state, _CYAN)
                self._state_lbl.config(text=f"◈  {state}", fg=color)
        except queue.Empty:
            pass
        try:
            while True:
                text, tag = _text_q.get_nowait()
                self._enqueue_type(text.rstrip(), tag)
        except queue.Empty:
            pass
        if self._root:
            self._root.after(80, self._poll)

    # ──────────────────────────────────────────────────────────────────────
    # TYPING ANIMATION
    # ──────────────────────────────────────────────────────────────────────
    def _enqueue_type(self, text: str, tag: str):
        self._type_queue.append((text, tag))
        if not self._typing:
            self._next_message()

    def _next_message(self):
        if not self._type_queue:
            self._typing = False
            return
        self._typing = True
        text, tag    = self._type_queue.pop(0)

        # Write header immediately
        ts = datetime.datetime.now().strftime("%H:%M")
        self._log.config(state="normal")
        hdr = f"◈ YOU  {ts}\n" if tag == "you" else f"◈ AI   {ts}\n"
        self._log.insert(tk.END, hdr, "lbl_you" if tag == "you" else "lbl_ai")
        self._log.config(state="disabled")

        # Animate first 120 chars; dump the rest instantly after
        cut = 120
        if len(text) > cut:
            self._type_buf  = text[:cut]
            self._type_tail = text[cut:]
        else:
            self._type_buf  = text
            self._type_tail = ""

        self._type_pos = 0
        self._type_tag = tag
        self._type_step()

    def _type_step(self):
        if self._type_pos < len(self._type_buf):
            ch = self._type_buf[self._type_pos]
            self._log.config(state="normal")
            self._log.insert(tk.END, ch, self._type_tag)
            self._log.see(tk.END)
            self._log.config(state="disabled")
            self._type_pos += 1
            if self._root:
                self._root.after(13, self._type_step)
        else:
            # Flush remainder + spacing
            self._log.config(state="normal")
            if self._type_tail:
                self._log.insert(tk.END, self._type_tail, self._type_tag)
            self._log.insert(tk.END, "\n\n", self._type_tag)
            self._log.see(tk.END)
            self._log.config(state="disabled")
            if self._root:
                self._root.after(80, self._next_message)

    # ──────────────────────────────────────────────────────────────────────
    # INPUT
    # ──────────────────────────────────────────────────────────────────────
    def _submit(self, _=None):
        text = self._entry.get().strip()
        self._entry.delete(0, tk.END)
        if text:
            self._enqueue_type(text, "you")
            self._cb(text)

    # ──────────────────────────────────────────────────────────────────────
    # PUBLIC THREAD-SAFE API
    # ──────────────────────────────────────────────────────────────────────
    def show(self):
        if self._root:
            self._root.after(0, self._do_show)

    def _do_show(self):
        self._root.deiconify()
        self._root.state("zoomed")
        self._root.lift()
        self._root.attributes("-topmost", True)
        self._root.after(200, lambda: self._root.attributes("-topmost", False))
        if self._entry:
            self._entry.focus_set()

    def hide(self):
        if self._root:
            self._root.after(0, self._root.withdraw)

    def set_state(self, state: str):
        _state_q.put(state)

    def add_message(self, text: str, tag: str = "jarvis"):
        _text_q.put((text.rstrip(), tag))

    # ──────────────────────────────────────────────────────────────────────
    # ENTRY POINT (call on MAIN thread)
    # ──────────────────────────────────────────────────────────────────────
    def run(self, root: tk.Tk):
        self._root = root          # ← was missing; caused all NoneType errors
        self._build(root)
        root.after(0,   self._tick)
        root.after(50,  self._animate)
        root.after(80,  self._poll)
        root.mainloop()
