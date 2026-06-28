"""painel.py — Painel principal CACTO (usuário e admin)."""
import tkinter as tk
from tkinter import font as tkfont, messagebox
from datetime import datetime
import threading
import config as cfg

BG, BG2, BG3  = "#0a1628", "#0d1e35", "#1a2a3a"
ACCENT        = "#00d4ff"
FG, FG_SUB    = "#ffffff", "#888888"
GREEN, YELLOW, RED, ORANGE = "#00cc66", "#ffaa00", "#ff4444", "#ff8800"
W, H          = 520, 700

_LEVEL_NAME = {1:"Girino",2:"Peixinho",3:"Golfinho",4:"Tubarão",5:"Baleia",6:"Oceano"}
_XP_NEXT    = {1:500, 2:1500, 3:4000, 4:10000, 5:25000, 6:None}
_MEDAL      = {1:"👑", 2:"🥈", 3:"🥉"}


class PainelWindow(tk.Toplevel):
    def __init__(self, master, api):
        super().__init__(master)
        self._api      = api
        self._is_admin = bool(cfg.get("is_admin", False))
        self._session  = {}
        self._ranking  = []
        self._drag     = (0, 0)

        self.overrideredirect(True)
        self.configure(bg=ACCENT)       # borda ciano 1px
        self.geometry(f"{W}x{H}")
        self._center()
        self._build()
        self._tick()
        self.after(500, self._bg_refresh)
        self._schedule_loops()

    def _center(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

    # ═══════════════════════════════════════════════════════════════════════
    # Layout principal
    # ═══════════════════════════════════════════════════════════════════════

    def _build(self):
        inner = tk.Frame(self, bg=BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self._build_titlebar(inner)

        cnv = tk.Canvas(inner, bg=BG, highlightthickness=0, bd=0)
        sb  = tk.Scrollbar(inner, orient="vertical", command=cnv.yview)
        cnv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cnv.pack(side="left", fill="both", expand=True)

        self._content = tk.Frame(cnv, bg=BG)
        cid = cnv.create_window((0, 0), window=self._content, anchor="nw")

        def _resize(e):
            cnv.configure(scrollregion=cnv.bbox("all"))
            cnv.itemconfig(cid, width=e.width)
        cnv.bind("<Configure>", _resize)
        cnv.bind_all("<MouseWheel>",
                     lambda e: cnv.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self._build_content()

    def _build_titlebar(self, parent):
        bar = tk.Frame(parent, bg=BG2, height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        logo = tk.Label(bar, text="🌵 CACTO",
                        font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
                        fg=ACCENT, bg=BG2)
        logo.pack(side="left", padx=12)

        for sym, hover in [("✕", RED), ("—", FG)]:
            tk.Button(bar, text=sym, font=("Segoe UI", 10),
                      fg=FG_SUB, bg=BG2,
                      activebackground="#111827", activeforeground=hover,
                      relief="flat", cursor="hand2", bd=0,
                      command=self.withdraw).pack(side="right", padx=4, pady=6)

        for w in (bar, logo):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

    def _drag_start(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _build_content(self):
        f = self._content
        self._build_user_card(f)
        if self._is_admin:
            self._build_session_ctrl(f)
        self._build_countdown(f)
        self._build_ranking(f)
        self._build_footer(f)

    # ═══════════════════════════════════════════════════════════════════════
    # Card pessoal
    # ═══════════════════════════════════════════════════════════════════════

    def _build_user_card(self, f):
        card = tk.Frame(f, bg=BG3)
        card.pack(fill="x", padx=12, pady=(10, 6))

        name   = cfg.get("name", "?") or "?"
        lvl    = cfg.get("level", 1)
        streak = cfg.get("streak_current", 0)
        xp     = cfg.get("xp_total", 0)

        row = tk.Frame(card, bg=BG3)
        row.pack(fill="x", padx=10, pady=(10, 4))

        # Avatar circular
        av = tk.Canvas(row, width=44, height=44, bg=BG3, highlightthickness=0)
        av.pack(side="left", padx=(0, 10))
        av.create_oval(2, 2, 42, 42, fill=BG2, outline=ACCENT, width=2)
        av.create_text(22, 22, text=name[0].upper(),
                       font=tkfont.Font(family="Segoe UI", size=18, weight="bold"),
                       fill=ACCENT)

        info = tk.Frame(row, bg=BG3)
        info.pack(side="left", fill="x", expand=True)

        tk.Label(info, text=name,
                 font=tkfont.Font(family="Segoe UI", size=13, weight="bold"),
                 fg=FG, bg=BG3, anchor="w").pack(anchor="w")
        self._lbl_level = tk.Label(
            info, text=f"Nível {lvl} — {_LEVEL_NAME.get(lvl, 'Girino')}",
            font=("Segoe UI", 9), fg=ACCENT, bg=BG3, anchor="w")
        self._lbl_level.pack(anchor="w")

        # Barra XP
        xp_row = tk.Frame(card, bg=BG3)
        xp_row.pack(fill="x", padx=10)
        self._lbl_xp = tk.Label(xp_row, text=f"XP {xp:,}",
                                  font=("Segoe UI", 8), fg=FG_SUB, bg=BG3)
        self._lbl_xp.pack(side="left")
        xp_next = _XP_NEXT.get(lvl)
        if xp_next:
            tk.Label(xp_row, text=f"→ {xp_next:,}", font=("Segoe UI", 8),
                     fg="#334455", bg=BG3).pack(side="right")

        self._cnv_xp = tk.Canvas(card, height=6, bg=BG2, highlightthickness=0)
        self._cnv_xp.pack(fill="x", padx=10, pady=(2, 8))
        self._bar_xp = self._cnv_xp.create_rectangle(0, 0, 0, 6, fill=ACCENT, outline="")

        # 3 blocos de stat
        gr = tk.Frame(card, bg=BG3)
        gr.pack(fill="x", padx=6, pady=(0, 8))
        gr.columnconfigure((0, 1, 2), weight=1)

        self._lbl_alarmes = self._stat_block(gr, 0, "alarmes hoje", "—/—")
        self._lbl_streak  = self._stat_block(gr, 1, "streak",       f"🔥 {streak}")
        self._lbl_rank    = self._stat_block(gr, 2, "rank hoje",    "#—")

    def _stat_block(self, parent, col, label, value):
        f = tk.Frame(parent, bg=BG2, pady=6)
        f.grid(row=0, column=col, sticky="nsew", padx=3, pady=2)
        lbl = tk.Label(f, text=value,
                       font=tkfont.Font(family="Segoe UI", size=14, weight="bold"),
                       fg=FG, bg=BG2)
        lbl.pack()
        tk.Label(f, text=label, font=("Segoe UI", 7), fg=FG_SUB, bg=BG2).pack()
        return lbl

    # ═══════════════════════════════════════════════════════════════════════
    # Countdown
    # ═══════════════════════════════════════════════════════════════════════

    def _build_countdown(self, f):
        box = tk.Frame(f, bg=BG, pady=8)
        box.pack(fill="x", padx=12)
        tk.Label(box, text="PRÓXIMO ALARME", font=("Segoe UI", 9),
                 fg="#555555", bg=BG).pack()
        self._lbl_cd = tk.Label(
            box, text="--:--",
            font=tkfont.Font(family="Consolas", size=42, weight="bold"),
            fg=ACCENT, bg=BG)
        self._lbl_cd.pack()
        self._lbl_cd_sub = tk.Label(box, text="", font=("Segoe UI", 8),
                                     fg=FG_SUB, bg=BG)
        self._lbl_cd_sub.pack()

    def _tick(self):
        try:
            self._update_countdown()
        except tk.TclError:
            return
        self.after(1000, self._tick)

    def _update_countdown(self):
        s = self._session
        if not s.get("is_active"):
            self._lbl_cd.config(
                text="SEM SESSÃO",
                font=tkfont.Font(family="Segoe UI", size=22, weight="bold"),
                fg="#444444")
            self._lbl_cd_sub.config(text="aguardando sessão ser iniciada")
            return
        if s.get("is_paused"):
            self._lbl_cd.config(
                text="⏸ PAUSADA",
                font=tkfont.Font(family="Segoe UI", size=24, weight="bold"),
                fg=ORANGE)
            self._lbl_cd_sub.config(text="sessão pausada")
            return

        naa = s.get("next_alarm_at")
        if not naa:
            self._lbl_cd.config(
                text="--:--",
                font=tkfont.Font(family="Consolas", size=42, weight="bold"),
                fg=ACCENT)
            self._lbl_cd_sub.config(text="")
            return

        try:
            secs = max(0, int(
                (datetime.fromisoformat(naa) - datetime.utcnow()).total_seconds()))
        except Exception:
            return

        m, s_ = divmod(secs, 60)
        if secs <= 60:
            color = BG if secs % 2 == 0 else RED   # pisca
        else:
            color = ACCENT
        self._lbl_cd.config(
            text=f"{m:02d}:{s_:02d}",
            font=tkfont.Font(family="Consolas", size=42, weight="bold"),
            fg=color)
        self._lbl_cd_sub.config(text="")

    # ═══════════════════════════════════════════════════════════════════════
    # Admin: controle de sessão
    # ═══════════════════════════════════════════════════════════════════════

    def _build_session_ctrl(self, f):
        card = tk.Frame(f, bg=BG2,
                        highlightthickness=1, highlightbackground=ACCENT)
        card.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(card, text="CONTROLE DA SESSÃO",
                 font=("Segoe UI", 8, "bold"), fg=ACCENT, bg=BG2
                 ).pack(anchor="w", padx=12, pady=(8, 2))

        self._lbl_sess_state = tk.Label(
            card, text="○ INATIVA",
            font=("Segoe UI", 11, "bold"), fg=FG_SUB, bg=BG2)
        self._lbl_sess_state.pack(pady=(0, 4))

        self._btn_row = tk.Frame(card, bg=BG2)
        self._btn_row.pack(fill="x", padx=10, pady=(0, 8))

        tk.Frame(card, bg=BG3, height=1).pack(fill="x", padx=12)

        tk.Label(card, text="ONLINE AGORA", font=("Segoe UI", 7, "bold"),
                 fg="#445566", bg=BG2).pack(anchor="w", padx=12, pady=(6, 0))
        self._lbl_online = tk.Label(
            card, text="—", font=("Segoe UI", 9),
            fg=GREEN, bg=BG2, wraplength=460, justify="left")
        self._lbl_online.pack(anchor="w", padx=12, pady=(0, 8))

    def _rebuild_session_btns(self):
        if not self._is_admin:
            return
        for w in self._btn_row.winfo_children():
            w.destroy()

        s      = self._session
        active = bool(s.get("is_active"))
        paused = bool(s.get("is_paused"))
        key    = cfg.get("token", "")

        if not active:
            self._lbl_sess_state.config(text="○ INATIVA", fg=FG_SUB)
            self._mkbtn("▶  INICIAR SESSÃO", ACCENT, BG,
                        lambda: self._sess_action("start", key), full=True)
        elif paused:
            self._lbl_sess_state.config(text="⏸  PAUSADA", fg=ORANGE)
            self._mkbtn("▶  RETOMAR PARA TODOS", GREEN, BG,
                        lambda: self._sess_action("resume", key))
            self._mkbtn("■  ENCERRAR", BG3, RED,
                        lambda: self._sess_action("end", key), border=RED)
        else:
            self._lbl_sess_state.config(text="●  ATIVA", fg=GREEN)
            self._mkbtn("⏸  PAUSAR PARA TODOS", ORANGE, FG,
                        lambda: self._sess_action("pause", key))
            self._mkbtn("■  ENCERRAR", BG3, RED,
                        lambda: self._sess_action("end", key), border=RED)

    def _mkbtn(self, text, bg, fg, cmd, full=False, border=None):
        kw = dict(text=text, bg=bg, fg=fg,
                  activebackground=bg, activeforeground=fg,
                  relief="flat", cursor="hand2", pady=8,
                  font=tkfont.Font(family="Segoe UI", size=10, weight="bold"),
                  command=cmd)
        if border:
            kw.update(highlightthickness=1, highlightbackground=border)
        btn = tk.Button(self._btn_row, **kw)
        if full:
            btn.pack(fill="x")
        else:
            btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        return btn

    def _sess_action(self, action: str, key: str):
        labels = {"start":"iniciar","pause":"pausar","resume":"retomar","end":"encerrar"}
        if not messagebox.askyesno("CACTO", f"Confirma {labels[action]} a sessão?",
                                    parent=self):
            return

        for w in self._btn_row.winfo_children():
            try:
                w.config(state="disabled", text="Aguardando...")
            except Exception:
                pass

        fn = {"start":  self._api.session_start,
              "pause":  self._api.session_pause,
              "resume": self._api.session_resume,
              "end":    self._api.session_end}[action]

        def _run():
            result = fn(key)
            self.after(0, lambda: self._on_sess_result(result))

        threading.Thread(target=_run, daemon=True).start()

    def _on_sess_result(self, result):
        if result is None:
            messagebox.showerror("CACTO", "Erro de rede. Tente novamente.", parent=self)
        else:
            self._session = result
        self._rebuild_session_btns()
        self._update_countdown()

    # ═══════════════════════════════════════════════════════════════════════
    # Ranking
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ranking(self, f):
        tk.Label(f, text="RANKING DO DIA", font=("Segoe UI", 8, "bold"),
                 fg=FG_SUB, bg=BG).pack(anchor="w", padx=14, pady=(6, 2))
        self._rank_frame = tk.Frame(f, bg=BG)
        self._rank_frame.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(self._rank_frame, text="Carregando...",
                 font=("Segoe UI", 9), fg=FG_SUB, bg=BG).pack()

    def _set_ranking(self, ranking: list):
        for w in self._rank_frame.winfo_children():
            w.destroy()

        my_name = cfg.get("name", "")
        for item in ranking[:10]:
            rank  = item.get("rank", 0)
            name  = item.get("name", "")
            pct   = float(item.get("pct", item.get("taxa_positiva", 0)))
            xp    = item.get("xp", item.get("xp_total", 0))
            is_me = name == my_name

            row_bg = "#0f2a1a" if is_me else BG
            row = tk.Frame(self._rank_frame, bg=row_bg,
                           highlightthickness=1 if is_me else 0,
                           highlightbackground=ACCENT, pady=4)
            row.pack(fill="x", pady=1)

            medal = _MEDAL.get(rank, f"#{rank}")
            tk.Label(row, text=str(medal), font=("Segoe UI", 10),
                     fg=ACCENT if rank <= 3 else FG_SUB,
                     bg=row_bg, width=3).pack(side="left", padx=(6, 2))

            tk.Label(row, text=name[:16],
                     font=tkfont.Font(family="Segoe UI", size=9,
                                      weight="bold" if is_me else "normal"),
                     fg=FG, bg=row_bg, width=14, anchor="w").pack(side="left")

            bar_f = tk.Frame(row, bg=BG3, width=80, height=6)
            bar_f.pack(side="left", padx=4)
            bar_f.pack_propagate(False)
            fill_w = int(80 * min(pct, 1.0))
            if fill_w:
                tk.Frame(bar_f, bg=GREEN if pct >= 0.75 else YELLOW,
                         width=fill_w, height=6).place(x=0, y=0)

            tk.Label(row, text=f"{round(pct*100)}%", font=("Segoe UI", 8),
                     fg=FG_SUB, bg=row_bg, width=4).pack(side="left")
            tk.Label(row, text=f"{xp}xp", font=("Segoe UI", 8),
                     fg=FG_SUB, bg=row_bg).pack(side="left", padx=(2, 6))

    # ═══════════════════════════════════════════════════════════════════════
    # Footer
    # ═══════════════════════════════════════════════════════════════════════

    def _build_footer(self, f):
        foot = tk.Frame(f, bg=BG2, height=28)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        self._lbl_foot = tk.Label(foot, text="", font=("Segoe UI", 8),
                                   fg=FG_SUB, bg=BG2)
        self._lbl_foot.pack(side="left", padx=12, pady=6)
        tk.Label(foot, text="v1.0.0", font=("Segoe UI", 8),
                 fg="#334455", bg=BG2).pack(side="right", padx=12)

    # ═══════════════════════════════════════════════════════════════════════
    # Refresh de dados
    # ═══════════════════════════════════════════════════════════════════════

    def _schedule_loops(self):
        self.after(5_000,  self._fast_tick)
        self.after(30_000, self._slow_tick)

    def _fast_tick(self):
        threading.Thread(target=self._fetch_fast, daemon=True).start()
        self.after(5_000, self._fast_tick)

    def _slow_tick(self):
        threading.Thread(target=self._fetch_slow, daemon=True).start()
        self.after(30_000, self._slow_tick)

    def _bg_refresh(self):
        threading.Thread(target=self._fetch_all, daemon=True).start()

    def _fetch_all(self):
        self._fetch_fast()
        self._fetch_slow()

    def _fetch_fast(self):
        session = self._api.get_session()
        team    = self._api.get_team_stats()
        online  = self._api.get_online() if self._is_admin else None
        self.after(0, lambda: self._apply_fast(session, team, online))

    def _fetch_slow(self):
        stats   = self._api.get_my_stats()
        ranking = self._api.get_ranking("day")
        self.after(0, lambda: self._apply_slow(stats, ranking))

    def _apply_fast(self, session, team, online):
        try:
            if session is not None:
                self._session = session
                self._update_countdown()
                if self._is_admin:
                    self._rebuild_session_btns()

            if team:
                n   = team.get("total_online", team.get("users_online", 0))
                pct = int(team.get("team_pct_today", team.get("taxa_equipe", 0)))
                self._lbl_foot.config(text=f"● {n} online  |  Time: {pct}% hoje")

            if self._is_admin and isinstance(online, list):
                txt = "  ".join(f"● {u['name']}" for u in online) if online else "ninguém online"
                self._lbl_online.config(text=txt)
        except tk.TclError:
            pass

    def _apply_slow(self, stats, ranking):
        try:
            if stats:
                self._update_user_stats(stats)
            if isinstance(ranking, list):
                self._ranking = ranking
                self._set_ranking(ranking)
                self._update_my_rank(ranking)
        except tk.TclError:
            pass

    def _update_user_stats(self, stats: dict):
        lvl    = stats.get("level",          cfg.get("level", 1))
        xp     = stats.get("xp_total",       cfg.get("xp_total", 0))
        streak = stats.get("streak_current", cfg.get("streak_current", 0))

        hist  = stats.get("historico_7_dias", [])
        today = hist[-1] if hist else {}
        pos   = today.get("alarms_positive", 0)
        total = today.get("alarms_total", 0)

        self._lbl_level.config(text=f"Nível {lvl} — {_LEVEL_NAME.get(lvl,'Girino')}")
        self._lbl_xp.config(text=f"XP {xp:,}")
        self._lbl_streak.config(text=f"🔥 {streak}")
        self._lbl_alarmes.config(text=f"{pos}/{total}")

        xp_next = _XP_NEXT.get(lvl)
        if xp_next:
            self._cnv_xp.update_idletasks()
            w = max(1, self._cnv_xp.winfo_width())
            self._cnv_xp.coords(self._bar_xp, 0, 0,
                                 int(w * min(xp / xp_next, 1.0)), 6)

    def _update_my_rank(self, ranking: list):
        my_name = cfg.get("name", "")
        for item in ranking:
            if item.get("name") == my_name:
                self._lbl_rank.config(text=f"#{item['rank']}")
                return

    def show_and_focus(self):
        self.deiconify()
        self.lift()
        self.focus_force()


def show(master, api, user_name: str = "", user_id: int = 0) -> PainelWindow:
    return PainelWindow(master, api)
