"""Janela de painel: ranking do dia, stats pessoais, status do time."""
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
import threading

BG     = "#0a1628"
BG2    = "#1a2a3a"
ACCENT = "#00d4ff"
FG     = "#ffffff"
FG_SUB = "#888888"
GREEN  = "#00cc66"
YELLOW = "#ffaa00"


class PainelWindow(tk.Toplevel):
    def __init__(self, master, api, user_name: str, user_id: int):
        super().__init__(master)
        self.title("🌵 CACTO — Painel")
        self.geometry("480x600")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._api = api
        self._user_name = user_name
        self._user_id = user_id
        self._center()
        self._build_ui()
        self.after(200, self._refresh_bg)

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"480x600+{(sw - 480)//2}+{(sh - 600)//2}")

    def _build_ui(self):
        # ── Cabeçalho pessoal ────────────────────────────────────
        hdr = tk.Frame(self, bg=BG, pady=12)
        hdr.pack(fill="x")

        self._lbl_name = tk.Label(
            hdr, text=self._user_name,
            font=tkfont.Font(family="Segoe UI", size=18, weight="bold"),
            fg=FG, bg=BG,
        )
        self._lbl_name.pack()

        self._lbl_level = tk.Label(hdr, text="Carregando...",
                                    font=("Segoe UI", 12), fg=ACCENT, bg=BG)
        self._lbl_level.pack()

        self._lbl_xp = tk.Label(hdr, text="", font=("Segoe UI", 10), fg=FG_SUB, bg=BG)
        self._lbl_xp.pack()

        self._lbl_streak = tk.Label(hdr, text="", font=("Segoe UI", 10), fg=FG_SUB, bg=BG)
        self._lbl_streak.pack()

        # ── Progresso diário ─────────────────────────────────────
        prog = tk.Frame(self, bg=BG, padx=20)
        prog.pack(fill="x", pady=(0, 8))

        self._lbl_meta = tk.Label(prog, text="", font=("Segoe UI", 9), fg=FG_SUB, bg=BG)
        self._lbl_meta.pack(anchor="w")

        self._cnv_prog = tk.Canvas(prog, height=8, bg=BG2, highlightthickness=0)
        self._cnv_prog.pack(fill="x")
        self._bar_prog = self._cnv_prog.create_rectangle(0, 0, 0, 8, fill=ACCENT, outline="")

        # ── Separador ────────────────────────────────────────────
        tk.Frame(self, bg="#2a3a4a", height=1).pack(fill="x", padx=20, pady=4)

        tk.Label(
            self, text="Ranking do dia",
            font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
            fg=FG, bg=BG,
        ).pack(pady=(4, 2))

        # ── Ranking ──────────────────────────────────────────────
        self._rank_frame = tk.Frame(self, bg=BG)
        self._rank_frame.pack(fill="both", expand=True, padx=20)

        # ── Status do time ───────────────────────────────────────
        tk.Frame(self, bg="#2a3a4a", height=1).pack(fill="x", padx=20, pady=4)

        self._lbl_team  = tk.Label(self, text="", font=("Segoe UI", 9), fg=FG_SUB, bg=BG)
        self._lbl_team.pack()
        self._lbl_next  = tk.Label(self, text="", font=("Segoe UI", 9), fg=FG_SUB, bg=BG)
        self._lbl_next.pack()

        # ── Botão atualizar ──────────────────────────────────────
        tk.Button(
            self, text="⟳  Atualizar",
            font=("Segoe UI", 10), fg=BG, bg=ACCENT,
            activebackground="#00b8e0", relief="flat", cursor="hand2",
            command=lambda: threading.Thread(target=self._refresh_bg, daemon=True).start(),
        ).pack(pady=10)

    # ── Refresh ─────────────────────────────────────────────────────

    def _refresh_bg(self):
        my_stats = self._api.get_my_stats()
        ranking  = self._api.get_ranking("day")
        team     = self._api.get_team_stats()
        try:
            if my_stats:
                self.after(0, lambda: self._set_my_stats(my_stats))
            if ranking:
                self.after(0, lambda: self._set_ranking(ranking))
            if team:
                self.after(0, lambda: self._set_team(team))
        except tk.TclError:
            pass  # janela foi fechada

    def refresh(self):
        threading.Thread(target=self._refresh_bg, daemon=True).start()

    # ── Dados ───────────────────────────────────────────────────────

    def _set_my_stats(self, data: dict):
        lvl  = data.get("level", 1)
        name = data.get("level_name", "Girino")
        self._lbl_level.config(text=f"Nível {lvl} — {name}")
        self._lbl_xp.config(text=f"XP total: {data.get('xp_total', 0):,}")
        self._lbl_streak.config(text=f"🔥 {data.get('streak_current', 0)} dias seguidos")

        hist  = data.get("historico_7_dias", [])
        today = hist[-1] if hist else {}
        pos   = today.get("alarms_positive", 0)
        total = today.get("alarms_total", 0)
        pct   = round(pos / total * 100) if total else 0
        self._lbl_meta.config(text=f"Meta hoje: {pos}/{total} alarmes ({pct}%)")

        self._cnv_prog.update_idletasks()
        bar_total = self._cnv_prog.winfo_width() or 440
        bar_w     = int(bar_total * min(pct / 100, 1.0))
        color     = GREEN if pct >= 75 else YELLOW
        self._cnv_prog.itemconfig(self._bar_prog, fill=color)
        self._cnv_prog.coords(self._bar_prog, 0, 0, bar_w, 8)

    def _set_ranking(self, ranking: list):
        for w in self._rank_frame.winfo_children():
            w.destroy()

        import config
        my_name = config.get("name", "")

        # Cabeçalho
        hdr = tk.Frame(self._rank_frame, bg=BG)
        hdr.pack(fill="x", pady=(2, 4))
        for col_idx, (txt, w) in enumerate(
            [("#", 3), ("Nome", 18), ("%", 5), ("XP", 7), ("🔥", 5)]
        ):
            tk.Label(
                hdr, text=txt, width=w, anchor="w",
                font=tkfont.Font(family="Segoe UI", size=8, weight="bold"),
                fg=FG_SUB, bg=BG,
            ).grid(row=0, column=col_idx, sticky="w")

        for item in ranking[:10]:
            is_me  = item.get("name") == my_name
            row_bg = BG2 if is_me else BG
            row    = tk.Frame(self._rank_frame, bg=row_bg, pady=2)
            row.pack(fill="x")

            pct_str = f"{round(item.get('pct', 0) * 100)}%"
            cols = [
                (str(item.get("rank", "")), 3),
                (item.get("name", "")[:16], 18),
                (pct_str, 5),
                (str(item.get("xp", 0)), 7),
                (str(item.get("streak", 0)), 5),
            ]
            for col_idx, (val, w) in enumerate(cols):
                tk.Label(
                    row, text=val, width=w, anchor="w",
                    font=("Segoe UI", 9),
                    fg=FG if is_me else FG_SUB,
                    bg=row_bg,
                ).grid(row=0, column=col_idx, sticky="w", padx=2)

    def _set_team(self, data: dict):
        online = data.get("total_online", 0)
        pct    = data.get("team_pct_today", 0)
        self._lbl_team.config(text=f"{online} online agora · Time: {pct}% hidratado hoje")

        naa = data.get("next_alarm_at")
        if naa:
            try:
                diff = int((datetime.fromisoformat(naa) - datetime.utcnow()).total_seconds())
                if diff > 0:
                    m, s = divmod(diff, 60)
                    self._lbl_next.config(text=f"Próximo alarme em: {m:02d}:{s:02d}")
                else:
                    self._lbl_next.config(text="Próximo alarme: agora!")
            except Exception:
                self._lbl_next.config(text="")
        else:
            self._lbl_next.config(text="Sessão não ativa")


def show(master, api, user_name: str, user_id: int) -> PainelWindow:
    win = PainelWindow(master, api, user_name, user_id)
    return win
