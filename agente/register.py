"""Cadastro/login — aparece apenas no primeiro uso."""
import tkinter as tk
from tkinter import font as tkfont
import threading

BG, BG2 = "#0a1628", "#1a2a3a"
ACCENT, FG, FG_SUB, FG_ERR = "#00d4ff", "#ffffff", "#666666", "#ff4444"
W, H = 400, 520


class RegisterWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CACTO — Entrar no time")
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._success = False
        self._mode = "register"
        self._frame = tk.Frame(self, bg=BG)
        self._frame.pack(fill="both", expand=True, padx=30, pady=16)
        self._center()
        self._render()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

    def _switch(self, mode: str):
        self._mode = mode
        self._render()

    def _render(self):
        for w in self._frame.winfo_children():
            w.destroy()
        f = self._frame

        # Logo
        tk.Label(f, text="🌵 CACTO",
                 font=tkfont.Font(family="Segoe UI", size=26, weight="bold"),
                 fg=ACCENT, bg=BG).pack(pady=(0, 2))
        tk.Label(f, text="Hidratação coletiva do Quatro5",
                 font=("Segoe UI", 10), fg=FG_SUB, bg=BG).pack(pady=(0, 14))

        # ── Tabs ──────────────────────────────────────────────────────
        tabs = tk.Frame(f, bg=BG)
        tabs.pack(fill="x", pady=(0, 14))

        active_font   = tkfont.Font(family="Segoe UI", size=11, weight="bold", underline=True)
        inactive_font = tkfont.Font(family="Segoe UI", size=11)

        for text, mode in [("Criar conta", "register"), ("Já tenho conta", "login")]:
            is_active = self._mode == mode
            lbl = tk.Label(
                tabs, text=text,
                font=active_font if is_active else inactive_font,
                fg=FG if is_active else "#555555",
                bg=BG, cursor="" if is_active else "hand2",
            )
            lbl.pack(side="left", padx=(0, 18))
            if not is_active:
                lbl.bind("<Button-1>", lambda e, m=mode: self._switch(m))

        # ── Campos ────────────────────────────────────────────────────
        fields = tk.Frame(f, bg=BG)
        fields.pack(fill="x")

        if self._mode == "register":
            self._name_var = tk.StringVar()
            self._field(fields, "Nome", self._name_var)

        self._email_var = tk.StringVar()
        self._field(fields, "Email", self._email_var)

        self._pass_var = tk.StringVar()
        self._field_pw(fields, "Senha", self._pass_var)

        if self._mode == "register":
            self._pass2_var = tk.StringVar()
            self._field_pw(fields, "Confirmar senha", self._pass2_var)

        # ── Erro ──────────────────────────────────────────────────────
        self._lbl_err = tk.Label(f, text="", font=("Segoe UI", 9), fg=FG_ERR, bg=BG)
        self._lbl_err.pack(pady=(4, 2))

        # ── Botão principal ───────────────────────────────────────────
        is_reg = self._mode == "register"
        self._btn = tk.Button(
            f,
            text="ENTRAR NO TIME" if is_reg else "ENTRAR",
            font=tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            fg=BG, bg=ACCENT,
            activebackground="#00b8e0", activeforeground=BG,
            relief="flat", cursor="hand2",
            command=self._do_register if is_reg else self._do_login,
        )
        self._btn.pack(fill="x", pady=(4, 8), ipady=10)

        # ── Link alternativo ──────────────────────────────────────────
        link_text = "Já tem conta? Entrar →" if is_reg else "← Criar nova conta"
        link_mode = "login" if is_reg else "register"
        lnk = tk.Label(f, text=link_text, font=("Segoe UI", 9),
                       fg=ACCENT, bg=BG, cursor="hand2")
        lnk.pack()
        lnk.bind("<Button-1>", lambda e, m=link_mode: self._switch(m))

    # ── Helpers de campo ──────────────────────────────────────────────

    def _field(self, parent, label: str, var: tk.StringVar):
        tk.Label(parent, text=label, font=("Segoe UI", 9),
                 fg=FG_SUB, bg=BG).pack(anchor="w")
        tk.Entry(parent, textvariable=var, font=("Segoe UI", 11),
                 bg=BG2, fg=FG, insertbackground=ACCENT,
                 relief="flat").pack(fill="x", pady=(2, 8), ipady=6)

    def _field_pw(self, parent, label: str, var: tk.StringVar):
        """Campo de senha com botão 👁 para mostrar/ocultar."""
        tk.Label(parent, text=label, font=("Segoe UI", 9),
                 fg=FG_SUB, bg=BG).pack(anchor="w")
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=(2, 8))
        e = tk.Entry(row, textvariable=var, font=("Segoe UI", 11),
                     bg=BG2, fg=FG, insertbackground=ACCENT,
                     relief="flat", show="*", bd=0, highlightthickness=0)
        e.pack(side="left", fill="x", expand=True, ipady=6, padx=(6, 0))
        tk.Button(
            row, text="👁", command=lambda: e.config(show="" if e.cget("show") else "*"),
            bg=BG2, fg="#555566", activebackground=BG2, activeforeground=FG,
            relief="flat", cursor="hand2", font=("Segoe UI", 10), bd=0,
        ).pack(side="right", padx=(0, 4))

    # ── Estado do botão ───────────────────────────────────────────────

    def _err(self, msg: str):
        self._lbl_err.config(text=msg)

    def _busy(self, on: bool):
        label = "Entrando..." if on else ("ENTRAR NO TIME" if self._mode == "register" else "ENTRAR")
        self._btn.config(state="disabled" if on else "normal", text=label)

    # ── Cadastro ──────────────────────────────────────────────────────

    def _do_register(self):
        name  = self._name_var.get().strip()
        email = self._email_var.get().strip()
        pwd   = self._pass_var.get()
        pwd2  = self._pass2_var.get()

        if not name:                    self._err("Preencha seu nome");                    return
        if "@" not in email:            self._err("Email inválido");                       return
        if len(pwd) < 6:                self._err("Senha muito curta (mín. 6 caracteres)"); return
        if pwd != pwd2:                 self._err("As senhas não conferem");               return

        self._busy(True)
        threading.Thread(target=self._reg_thread, args=(name, email, pwd), daemon=True).start()

    def _reg_thread(self, name, email, pwd):
        import config
        from api import CactoAPI
        result = CactoAPI(config.get("backend_url"), "").register(name, email, pwd)
        self.after(0, lambda: self._on_reg(result, name, email))

    def _on_reg(self, result, name, email):
        if result is None:
            self._busy(False); self._err("Erro ao criar conta. Tente novamente."); return
        if result.get("error") == "email_exists":
            self._busy(False); self._err("Email já cadastrado"); return
        if result.get("error") == "no_connection":
            self._busy(False); self._err("Sem conexão com o servidor"); return
        import config
        d = config.load()
        d.update({
            "token":   result["token"],
            "user_id": result["user_id"],
            "name":    result.get("name", name),
            "email":   email,
            "level":   result.get("level", 1),
            "xp_total": result.get("xp_total", 0),
        })
        config.save(d)
        self._success = True
        self.quit()

    # ── Login ─────────────────────────────────────────────────────────

    def _do_login(self):
        email = self._email_var.get().strip()
        pwd   = self._pass_var.get()
        if "@" not in email: self._err("Email inválido"); return
        if not pwd:          self._err("Preencha a senha"); return

        self._busy(True)
        threading.Thread(target=self._login_thread, args=(email, pwd), daemon=True).start()

    def _login_thread(self, email, pwd):
        import config
        from api import CactoAPI
        result = CactoAPI(config.get("backend_url"), "").login(email, pwd)
        self.after(0, lambda: self._on_login(result, email))

    def _on_login(self, result, email):
        if result is None:
            self._busy(False); self._err("Erro ao entrar. Tente novamente."); return
        if result.get("error") == "invalid_credentials":
            self._busy(False); self._err("Email ou senha incorretos"); return
        if result.get("error") == "no_connection":
            self._busy(False); self._err("Sem conexão com o servidor"); return
        import config
        d = config.load()
        d.update({
            "token":          result["token"],
            "user_id":        result["user_id"],
            "name":           result.get("name", ""),
            "email":          email,
            "streak_current": result.get("streak_current", 0),
            "level":          result.get("level", 1),
            "xp_total":       result.get("xp_total", 0),
        })
        config.save(d)
        self._success = True
        self.quit()

    def show(self) -> bool:
        """Exibe a janela. Retorna True se autenticou com sucesso."""
        try:
            self.mainloop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        return self._success
