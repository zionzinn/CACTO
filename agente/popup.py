"""
Popup Central (Modo 1) — janela tkinter sempre-no-topo, 380×280px.
Fase 2: único modo implementado.
"""
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
from typing import Callable

BG       = "#0a1628"
ACCENT   = "#00d4ff"
DRINK_BG = "#00d4ff"
DRINK_FG = "#0a1628"
EMPTY_BG = "#1a2a3a"
EMPTY_FG = "#aaaaaa"

TIMEOUT_SECS = 20
W, H = 380, 280


class PopupCentral(tk.Toplevel):
    def __init__(
        self,
        master,
        alarm_time: str,
        streak: int,
        xp_multiplier: float,
        on_drink: Callable,
        on_empty: Callable,
        on_timeout: Callable,
        on_pause: Callable,
        on_close: Callable = None,
    ):
        super().__init__(master)
        self._alarm_time = alarm_time
        self._streak = streak
        self._xp_mult = xp_multiplier
        self._on_drink = on_drink
        self._on_empty = on_empty
        self._on_timeout = on_timeout
        self._on_pause = on_pause
        self._on_close = on_close
        self._remaining = TIMEOUT_SECS
        self._answered = False
        self._closed = False

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=ACCENT)   # borda ciano via bg + inner frame
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)  # fechar = destroy → on_close

        self._center()
        self._build_ui()
        self.withdraw()  # show() vai deiconify

    def _center(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - W) // 2
        y = (sh - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")

    def _build_ui(self):
        # Borda 2px via padding no frame externo (bg=ACCENT)
        outer = tk.Frame(self, bg=ACCENT, padx=2, pady=2)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill="both", expand=True)

        # Botão X (fechar = timeout)
        tk.Button(
            inner, text="✕",
            font=("Segoe UI", 9), fg="#444466", bg=BG,
            activebackground=BG, activeforeground="#aaaaaa",
            relief="flat", cursor="hand2", bd=0,
            command=self._force_close,
        ).place(relx=1.0, x=-22, y=4, width=18, height=18)

        # Ícone cactus
        tk.Label(
            inner, text="🌵",
            font=("Segoe UI Emoji", 36), bg=BG, fg=ACCENT,
        ).pack(pady=(14, 0))

        # Título
        tk.Label(
            inner, text="HORA DE BEBER ÁGUA!",
            font=tkfont.Font(family="Segoe UI", size=14, weight="bold"),
            fg="#ffffff", bg=BG,
        ).pack()

        # Contador regressivo
        self._lbl_count = tk.Label(
            inner,
            text=f"fechando em {TIMEOUT_SECS}s",
            font=("Segoe UI", 9), fg="#666666", bg=BG,
        )
        self._lbl_count.pack(pady=(3, 2))

        # Barra de progresso
        self._cnv = tk.Canvas(inner, width=340, height=4, bg="#1a2a3a",
                              highlightthickness=0, bd=0)
        self._cnv.pack(pady=(0, 8))
        self._bar = self._cnv.create_rectangle(0, 0, 340, 4, fill=ACCENT, outline="")

        # Botões
        btn_frame = tk.Frame(inner, bg=BG)
        btn_frame.pack(pady=2)

        drink = tk.Button(
            btn_frame, text="💧 BEBI",
            font=tkfont.Font(family="Segoe UI", size=13, weight="bold"),
            fg=DRINK_FG, bg=DRINK_BG,
            activebackground="#00b8e0", activeforeground=DRINK_FG,
            relief="flat", cursor="hand2",
            command=self._drink_click,
        )
        drink.pack(side="left", padx=8, ipady=11, ipadx=8)
        drink.bind("<Enter>", lambda e: drink.config(bg="#00b8e0"))
        drink.bind("<Leave>", lambda e: drink.config(bg=DRINK_BG))

        empty = tk.Button(
            btn_frame, text="🪣 VAZIA",
            font=tkfont.Font(family="Segoe UI", size=13, weight="bold"),
            fg=EMPTY_FG, bg=EMPTY_BG,
            activebackground="#2a3a4a", activeforeground="#cccccc",
            relief="flat", cursor="hand2",
            command=self._empty_click,
        )
        empty.pack(side="left", padx=8, ipady=11, ipadx=8)
        empty.bind("<Enter>", lambda e: empty.config(bg="#2a3a4a"))
        empty.bind("<Leave>", lambda e: empty.config(bg=EMPTY_BG))

        # XP preview
        xp_base = 10
        xp_final = int(xp_base * self._xp_mult)
        if self._xp_mult > 1.0:
            preview = f"+{xp_base} XP ×{self._xp_mult} = {xp_final} XP"
        else:
            preview = f"+{xp_base} XP"

        tk.Label(inner, text=preview, font=("Segoe UI", 9), fg="#888888", bg=BG).pack(pady=(6, 2))

        # Pausar pop-ups
        tk.Button(
            inner, text="⏸ Pausar pop-ups ▾",
            font=("Segoe UI", 9), fg="#555555", bg=BG,
            activebackground=BG, activeforeground="#888888",
            relief="flat", cursor="hand2", bd=0,
            command=self._pause_menu,
        ).pack()

    # ── Controle ────────────────────────────────────────────────────

    def destroy(self):
        # Único ponto de saída: garante que on_close roda exatamente uma vez,
        # libere _popup_open mesmo se o popup fechar por um caminho inesperado.
        if not self._closed:
            self._closed = True
            if self._on_close:
                try:
                    self._on_close()
                except Exception:
                    pass
        super().destroy()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(1000, self._tick)

    def _tick(self):
        if self._answered:
            return
        self._remaining -= 1

        color = "#ff4444" if self._remaining <= 5 else "#666666"
        self._lbl_count.config(text=f"fechando em {self._remaining}s", fg=color)

        bar_w = max(0, int(340 * self._remaining / TIMEOUT_SECS))
        self._cnv.coords(self._bar, 0, 0, bar_w, 4)

        if self._remaining <= 0:
            self._do_timeout()
            return
        self.after(1000, self._tick)

    def _drink_click(self):
        if self._answered:
            return
        self._answered = True
        rt = datetime.utcnow().isoformat()
        cb = self._on_drink
        self.destroy()
        cb(rt)

    def _empty_click(self):
        if self._answered:
            return
        self._answered = True
        rt = datetime.utcnow().isoformat()
        cb = self._on_empty
        self.destroy()
        cb(rt)

    def _do_timeout(self):
        if self._answered:
            return
        self._answered = True
        cb = self._on_timeout
        self.destroy()
        cb()

    def _force_close(self):
        self._do_timeout()

    def _pause_menu(self):
        menu = tk.Menu(
            self, tearoff=0,
            bg="#1a2a3a", fg="#aaaaaa",
            activebackground="#2a3a4a", activeforeground="white",
            font=("Segoe UI", 10),
        )
        cb = self._on_pause
        menu.add_command(label="30 minutos", command=lambda: cb(30))
        menu.add_command(label="1 hora",     command=lambda: cb(60))
        menu.add_command(label="Hoje",       command=lambda: cb(480))
        menu.add_command(label="Reunião",    command=lambda: cb(90))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()
