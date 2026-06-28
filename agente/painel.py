"""painel.py — Painel principal CACTO (usuário e admin), tela cheia."""
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
import threading
import config as cfg

BG, BG2, BG3  = "#0a1628", "#0d1e35", "#1a2a3a"
ACCENT        = "#00d4ff"
FG, FG_SUB    = "#ffffff", "#888888"
GREEN, YELLOW, RED, ORANGE = "#00cc66", "#ffaa00", "#ff4444", "#ff8800"
RED_DIM       = "#ff9999"

_LEVEL_NAME = {1:"Girino",2:"Peixinho",3:"Golfinho",4:"Tubarão",5:"Baleia",6:"Oceano"}
_XP_NEXT    = {1:500, 2:1500, 3:4000, 4:10000, 5:25000, 6:None}
_MEDAL      = {1:"👑", 2:"🥈", 3:"🥉"}


class PainelWindow(tk.Toplevel):
    def __init__(self, master, api):
        super().__init__(master)
        self._api      = api
        self._is_admin = bool(cfg.get("is_admin", False))
        self._session  = {}
        self._last_team = None
        self._drag     = (0, 0)

        # Estado dos loops/flags
        self._cd_after      = None    # id do after() do countdown (1 único)
        self._cd_kind       = None    # "num" | "msg"
        self._blink         = False
        self._confirm_after = None    # id do timeout de confirmação inline
        self._reconn_after  = None    # id do flash "reconectado"
        self._was_offline   = False

        self.overrideredirect(True)
        self.configure(bg=ACCENT)     # borda ciano 1px
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")

        self._build()
        self._kick_tick()
        self.after(400, self._bg_refresh)
        self._schedule_loops()

    # ═══════════════════════════════════════════════════════════════════════
    # Layout principal (tela cheia)
    # ═══════════════════════════════════════════════════════════════════════

    def _build(self):
        inner = tk.Frame(self, bg=BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._build_titlebar(inner)
        self._build_footer(inner)          # fica no rodapé (side bottom)

        body = tk.Frame(inner, bg=BG)
        body.pack(fill="both", expand=True)
        self._build_content(body)

    def _build_titlebar(self, parent):
        bar = tk.Frame(parent, bg=BG2, height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        logo = tk.Label(bar, text="🌵 CACTO",
                        font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
                        fg=ACCENT, bg=BG2)
        logo.pack(side="left", padx=12)

        for sym, hover in [("✕", RED), ("—", FG)]:
            tk.Button(bar, text=sym, font=("Segoe UI", 11),
                      fg=FG_SUB, bg=BG2,
                      activebackground="#111827", activeforeground=hover,
                      relief="flat", cursor="hand2", bd=0, width=3,
                      command=self.withdraw).pack(side="right", padx=2, pady=4)

        for w in (bar, logo):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

    def _drag_start(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _build_content(self, body):
        col = tk.Frame(body, bg=BG)
        col.pack(fill="both", expand=True, padx=60, pady=10)

        self._build_user_card(col)
        if self._is_admin:
            self._build_session_ctrl(col)
        self._build_countdown(col)
        self._build_ranking(col)          # cresce verticalmente

    # ═══════════════════════════════════════════════════════════════════════
    # Card pessoal
    # ═══════════════════════════════════════════════════════════════════════

    def _build_user_card(self, f):
        card = tk.Frame(f, bg=BG3)
        card.pack(fill="x", pady=(4, 6))

        name   = cfg.get("name", "?") or "?"
        lvl    = cfg.get("level", 1)
        streak = cfg.get("streak_current", 0)
        xp     = cfg.get("xp_total", 0)

        row = tk.Frame(card, bg=BG3)
        row.pack(fill="x", padx=14, pady=(12, 4))

        av = tk.Canvas(row, width=48, height=48, bg=BG3, highlightthickness=0)
        av.pack(side="left", padx=(0, 12))
        av.create_oval(2, 2, 46, 46, fill=BG2, outline=ACCENT, width=2)
        av.create_text(24, 24, text=name[0].upper(),
                       font=tkfont.Font(family="Segoe UI", size=20, weight="bold"),
                       fill=ACCENT)

        info = tk.Frame(row, bg=BG3)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=name,
                 font=tkfont.Font(family="Segoe UI", size=15, weight="bold"),
                 fg=FG, bg=BG3, anchor="w").pack(anchor="w")
        self._lbl_level = tk.Label(
            info, text=f"Nível {lvl} — {_LEVEL_NAME.get(lvl, 'Girino')}",
            font=("Segoe UI", 10), fg=ACCENT, bg=BG3, anchor="w")
        self._lbl_level.pack(anchor="w")

        xp_row = tk.Frame(card, bg=BG3)
        xp_row.pack(fill="x", padx=14)
        self._lbl_xp = tk.Label(xp_row, text=f"XP {xp:,}",
                                font=("Segoe UI", 9), fg=FG_SUB, bg=BG3)
        self._lbl_xp.pack(side="left")
        xp_next = _XP_NEXT.get(lvl)
        if xp_next:
            tk.Label(xp_row, text=f"→ {xp_next:,}", font=("Segoe UI", 9),
                     fg="#334455", bg=BG3).pack(side="right")

        self._cnv_xp = tk.Canvas(card, height=7, bg=BG2, highlightthickness=0)
        self._cnv_xp.pack(fill="x", padx=14, pady=(3, 10))
        self._bar_xp = self._cnv_xp.create_rectangle(0, 0, 0, 7, fill=ACCENT, outline="")

        gr = tk.Frame(card, bg=BG3)
        gr.pack(fill="x", padx=10, pady=(0, 10))
        gr.columnconfigure((0, 1, 2), weight=1)
        self._lbl_alarmes = self._stat_block(gr, 0, "alarmes hoje", "—/—")
        self._lbl_streak  = self._stat_block(gr, 1, "streak",       f"🔥 {streak}")
        self._lbl_rank    = self._stat_block(gr, 2, "rank hoje",    "#—")

    def _stat_block(self, parent, col, label, value):
        f = tk.Frame(parent, bg=BG2, pady=8)
        f.grid(row=0, column=col, sticky="nsew", padx=4, pady=2)
        lbl = tk.Label(f, text=value,
                       font=tkfont.Font(family="Segoe UI", size=16, weight="bold"),
                       fg=FG, bg=BG2)
        lbl.pack()
        tk.Label(f, text=label, font=("Segoe UI", 8), fg=FG_SUB, bg=BG2).pack()
        return lbl

    # ═══════════════════════════════════════════════════════════════════════
    # Countdown — 1 único loop after(), label nunca recriado
    # ═══════════════════════════════════════════════════════════════════════

    def _build_countdown(self, f):
        box = tk.Frame(f, bg=BG, pady=10)
        box.pack(fill="x")
        tk.Label(box, text="PRÓXIMO ALARME", font=("Segoe UI", 11),
                 fg="#555555", bg=BG).pack()
        self._lbl_cd = tk.Label(box, text="--:--",
                                font=("Consolas", 72, "bold"), fg=ACCENT, bg=BG)
        self._lbl_cd.pack()
        self._cd_kind = "num"
        self._lbl_cd_sub = tk.Label(box, text="", font=("Segoe UI", 9),
                                    fg=FG_SUB, bg=BG)
        self._lbl_cd_sub.pack()

    def _kick_tick(self):
        """Garante que o loop visual do countdown está rodando (sem duplicar)."""
        if self._cd_after is None:
            self._tick()

    def _tick(self):
        self._cd_after = None
        try:
            keep = self._render_countdown()
        except tk.TclError:
            return
        if keep:
            self._cd_after = self.after(1000, self._tick)

    def _render_countdown(self) -> bool:
        """Atualiza o label. Retorna True se deve continuar o loop de 1s."""
        s = self._session
        if not s.get("is_active"):
            self._set_cd_msg("SEM SESSÃO", "#444444", "aguardando sessão ser iniciada")
            return False
        if s.get("is_paused"):
            self._set_cd_msg("⏸ PAUSADA", ORANGE, "sessão pausada para todos")
            return False

        naa = s.get("next_alarm_at")
        if not naa:
            self._set_cd_num("--:--", ACCENT)
            self._lbl_cd_sub.config(text="")
            return True
        try:
            secs = max(0, int(
                (datetime.fromisoformat(naa) - datetime.utcnow()).total_seconds()))
        except Exception:
            self._set_cd_num("--:--", ACCENT)
            return True

        m, s_ = divmod(secs, 60)
        if secs <= 60:
            self._blink = not self._blink
            color = RED if self._blink else RED_DIM   # pisca sem sumir
        else:
            color = ACCENT
        self._set_cd_num(f"{m:02d}:{s_:02d}", color)
        self._lbl_cd_sub.config(text="")
        return True

    def _set_cd_num(self, text, color):
        if self._cd_kind != "num":
            self._lbl_cd.config(font=("Consolas", 72, "bold"))
            self._cd_kind = "num"
        self._lbl_cd.config(text=text, fg=color)

    def _set_cd_msg(self, text, color, sub):
        if self._cd_kind != "msg":
            self._lbl_cd.config(font=("Segoe UI", 36, "bold"))
            self._cd_kind = "msg"
        self._lbl_cd.config(text=text, fg=color)
        self._lbl_cd_sub.config(text=sub)

    # ═══════════════════════════════════════════════════════════════════════
    # Admin: controle de sessão (confirmação inline, sem messagebox)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_session_ctrl(self, f):
        card = tk.Frame(f, bg=BG2, highlightthickness=1, highlightbackground=ACCENT)
        card.pack(fill="x", pady=(0, 6))

        tk.Label(card, text="CONTROLE DA SESSÃO", font=("Segoe UI", 9, "bold"),
                 fg=ACCENT, bg=BG2).pack(anchor="w", padx=14, pady=(10, 2))

        self._lbl_sess_state = tk.Label(card, text="○ INATIVA",
                                        font=("Segoe UI", 12, "bold"),
                                        fg=FG_SUB, bg=BG2)
        self._lbl_sess_state.pack(pady=(0, 6))

        self._btn_row = tk.Frame(card, bg=BG2)
        self._btn_row.pack(fill="x", padx=12, pady=(0, 10))

        tk.Frame(card, bg=BG3, height=1).pack(fill="x", padx=14)
        tk.Label(card, text="ONLINE AGORA", font=("Segoe UI", 8, "bold"),
                 fg="#445566", bg=BG2).pack(anchor="w", padx=14, pady=(8, 0))
        self._lbl_online = tk.Label(card, text="—", font=("Segoe UI", 10),
                                    fg=GREEN, bg=BG2, justify="left", anchor="w")
        self._lbl_online.pack(anchor="w", fill="x", padx=14, pady=(0, 10))

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
                        lambda: self._exec_session("start", key), full=True)
        elif paused:
            self._lbl_sess_state.config(text="⏸  PAUSADA", fg=ORANGE)
            self._mkbtn("▶  RETOMAR PARA TODOS", GREEN, BG,
                        lambda: self._exec_session("resume", key))
            self._mkbtn("■  ENCERRAR", BG3, RED,
                        lambda: self._ask_end(key), border=RED)
        else:
            self._lbl_sess_state.config(text="●  ATIVA", fg=GREEN)
            self._mkbtn("⏸  PAUSAR PARA TODOS", ORANGE, FG,
                        lambda: self._exec_session("pause", key))
            self._mkbtn("■  ENCERRAR", BG3, RED,
                        lambda: self._ask_end(key), border=RED)

    def _mkbtn(self, text, bg, fg, cmd, full=False, border=None):
        kw = dict(text=text, bg=bg, fg=fg,
                  activebackground=bg, activeforeground=fg,
                  relief="flat", cursor="hand2", pady=10,
                  font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
                  command=cmd)
        if border:
            kw.update(highlightthickness=1, highlightbackground=border)
        btn = tk.Button(self._btn_row, **kw)
        if full:
            btn.pack(fill="x")
        else:
            btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        return btn

    # ── Confirmação inline de encerramento ───────────────────────────────

    def _ask_end(self, key):
        for w in self._btn_row.winfo_children():
            w.destroy()
        self._mkbtn("✓  CONFIRMAR ENCERRAMENTO", RED, FG,
                    lambda: self._confirm_end(key))
        self._mkbtn("CANCELAR", BG3, FG_SUB, lambda: self._cancel_confirm())
        self._confirm_after = self.after(3000, self._cancel_confirm)

    def _cancel_confirm(self):
        if self._confirm_after is not None:
            try:
                self.after_cancel(self._confirm_after)
            except Exception:
                pass
            self._confirm_after = None
        self._rebuild_session_btns()

    def _confirm_end(self, key):
        if self._confirm_after is not None:
            try:
                self.after_cancel(self._confirm_after)
            except Exception:
                pass
            self._confirm_after = None
        self._exec_session("end", key)

    # ── Execução das ações de sessão ─────────────────────────────────────

    def _exec_session(self, action: str, key: str):
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
            self._lbl_sess_state.config(text="⚠ erro de rede — tente de novo", fg=RED)
        else:
            self._session = result
        self._rebuild_session_btns()
        self._kick_tick()

    # ═══════════════════════════════════════════════════════════════════════
    # Ranking
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ranking(self, f):
        tk.Label(f, text="RANKING DO DIA", font=("Segoe UI", 9, "bold"),
                 fg=FG_SUB, bg=BG).pack(anchor="w", pady=(8, 2))
        self._rank_frame = tk.Frame(f, bg=BG)
        self._rank_frame.pack(fill="both", expand=True)
        tk.Label(self._rank_frame, text="Carregando...",
                 font=("Segoe UI", 10), fg=FG_SUB, bg=BG).pack(pady=20)

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
                           highlightbackground=ACCENT)
            row.pack(fill="x", pady=2, ipady=4)

            medal = _MEDAL.get(rank, f"#{rank}")
            tk.Label(row, text=str(medal), font=("Segoe UI", 12),
                     fg=ACCENT if rank <= 3 else FG_SUB,
                     bg=row_bg, width=4).pack(side="left", padx=(8, 2))
            tk.Label(row, text=name[:20],
                     font=tkfont.Font(family="Segoe UI", size=11,
                                      weight="bold" if is_me else "normal"),
                     fg=FG, bg=row_bg, width=18, anchor="w").pack(side="left")

            bar_f = tk.Frame(row, bg=BG3, width=160, height=8)
            bar_f.pack(side="left", padx=8)
            bar_f.pack_propagate(False)
            fill_w = int(160 * min(pct, 1.0))
            if fill_w:
                tk.Frame(bar_f, bg=GREEN if pct >= 0.75 else YELLOW,
                         width=fill_w, height=8).place(x=0, y=0)

            tk.Label(row, text=f"{round(pct*100)}%", font=("Segoe UI", 10),
                     fg=FG_SUB, bg=row_bg, width=5).pack(side="left")
            tk.Label(row, text=f"{xp} XP", font=("Segoe UI", 10),
                     fg=FG_SUB, bg=row_bg).pack(side="right", padx=(2, 12))

    # ═══════════════════════════════════════════════════════════════════════
    # Rodapé + indicador de conexão
    # ═══════════════════════════════════════════════════════════════════════

    def _build_footer(self, parent):
        foot = tk.Frame(parent, bg=BG2, height=32)
        foot.pack(side="bottom", fill="x")
        foot.pack_propagate(False)
        self._lbl_foot = tk.Label(foot, text="● conectando...", font=("Segoe UI", 9),
                                  fg=FG_SUB, bg=BG2)
        self._lbl_foot.pack(side="left", padx=14, pady=7)
        tk.Label(foot, text="v1.0.0", font=("Segoe UI", 9),
                 fg="#334455", bg=BG2).pack(side="right", padx=14)

    def _set_conn(self, online: bool):
        if not online:
            self._lbl_foot.config(text="● sem conexão", fg=RED)
            self._was_offline = True
            return
        if self._was_offline:
            self._was_offline = False
            self._lbl_foot.config(text="● reconectado", fg=GREEN)
            if self._reconn_after is not None:
                try:
                    self.after_cancel(self._reconn_after)
                except Exception:
                    pass
            self._reconn_after = self.after(3000, self._render_footer_normal)
        else:
            self._render_footer_normal()

    def _render_footer_normal(self):
        self._reconn_after = None
        team = self._last_team
        try:
            if team:
                n   = team.get("total_online", team.get("users_online", 0))
                pct = int(team.get("team_pct_today", team.get("taxa_equipe", 0)))
                self._lbl_foot.config(text=f"● {n} online  |  Time: {pct}% hoje",
                                      fg=FG_SUB)
            else:
                self._lbl_foot.config(text="● online", fg=GREEN)
        except tk.TclError:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # Refresh de dados (separado do loop visual do countdown)
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
        threading.Thread(target=self._fetch_fast, daemon=True).start()
        threading.Thread(target=self._fetch_slow, daemon=True).start()

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
            offline = session is None
            if not offline:
                self._session = session
                self._kick_tick()
                # Não reconstrói botões no meio de uma confirmação inline
                if self._is_admin and self._confirm_after is None:
                    self._rebuild_session_btns()
            if team:
                self._last_team = team
            self._set_conn(not offline)

            if self._is_admin and isinstance(online, list):
                txt = "   ".join(f"● {u['name']}" for u in online) if online \
                      else "ninguém online"
                self._lbl_online.config(text=txt)
        except tk.TclError:
            pass

    def _apply_slow(self, stats, ranking):
        try:
            if stats:
                self._update_user_stats(stats)
            if isinstance(ranking, list):
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
                                int(w * min(xp / xp_next, 1.0)), 7)

    def _update_my_rank(self, ranking: list):
        my_name = cfg.get("name", "")
        for item in ranking:
            if item.get("name") == my_name:
                self._lbl_rank.config(text=f"#{item['rank']}")
                return

    # ═══════════════════════════════════════════════════════════════════════

    def show_and_focus(self):
        self.deiconify()
        self.lift()
        self.focus_force()


def show(master, api, *_ignored) -> PainelWindow:
    return PainelWindow(master, api)
