"""
Janela de cadastro/login. Aparece apenas no primeiro uso
(quando config.json não tem token).
"""
import tkinter as tk
from tkinter import font as tkfont
import threading

BG       = "#0a1628"
BG2      = "#1a2a3a"
ACCENT   = "#00d4ff"
FG       = "#ffffff"
FG_SUB   = "#666666"
FG_ERR   = "#ff4444"

W, H = 400, 500


class RegisterWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CACTO — Entrar no time")
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._center()
        self._success = False
        self._mode = "register"
        self._frame = tk.Frame(self, bg=BG)
        self._frame.pack(fill="both", expand=True, padx=30, pady=20)
        self._render()

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw - W)//2}+{(sh - H)//2}")

    def _clear(self):
        for w in self._frame.winfo_children():
            w.destroy()

    def _render(self):
        self._clear()
        f = self._frame

        tk.Label(
            f, text="🌵 CACTO",
            font=tkfont.Font(family="Segoe UI", size=28, weight="bold"),
            fg=ACCENT, bg=BG,
        ).pack(pady=(0, 4))
        tk.Label(
            f, text="Hidratação coletiva do Quatro5",
            font=("Segoe UI", 11), fg=FG_SUB, bg=BG,
        ).pack(pady=(0, 18))

        title = "Criar conta" if self._mode == "register" else "Entrar na conta"
        tk.Label(
            f, text=title,
            font=tkfont.Font(family="Segoe UI", size=13, weight="bold"),
            fg=FG, bg=BG,
        ).pack()

        fields = tk.Frame(f, bg=BG)
        fields.pack(pady=10, fill="x")

        if self._mode == "register":
            self._name_var = tk.StringVar()
            self._make_entry(fields, "Nome", self._name_var)

        self._email_var = tk.StringVar()
        self._make_entry(fields, "Email", self._email_var)

        self._pass_var = tk.StringVar()
        self._make_entry(fields, "Senha", self._pass_var, show="*")

        if self._mode == "register":
            self._pass2_var = tk.StringVar()
            self._make_entry(fields, "Confirmar senha", self._pass2_var, show="*")

        self._lbl_err = tk.Label(f, text="", font=("Segoe UI", 9), fg=FG_ERR, bg=BG)
        self._lbl_err.pack(pady=(0, 4))

        if self._mode == "register":
            btn_text, btn_cmd = "Entrar no time", self._do_register
        else:
            btn_text, btn_cmd = "Entrar", self._do_login

        tk.Button(
            f, text=btn_text,
            font=tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            fg=BG, bg=ACCENT,
            activebackground="#00b8e0", activeforeground=BG,
            relief="flat", cursor="hand2", pady=10,
            command=btn_cmd,
        ).pack(fill="x", pady=6)

        if self._mode == "register":
            link_text, link_cmd = "Já tenho conta? Entrar →", self._to_login
        else:
            link_text, link_cmd = "← Criar nova conta", self._to_register

        lbl = tk.Label(f, text=link_text, font=("Segoe UI", 10),
                       fg=ACCENT, bg=BG, cursor="hand2")
        lbl.pack()
        lbl.bind("<Button-1>", lambda e: link_cmd())

    def _make_entry(self, parent, label: str, var: tk.StringVar, show: str = ""):
        tk.Label(parent, text=label, font=("Segoe UI", 9),
                 fg=FG_SUB, bg=BG).pack(anchor="w")
        tk.Entry(
            parent, textvariable=var,
            font=("Segoe UI", 11), bg=BG2, fg=FG,
            insertbackground=ACCENT, relief="flat", show=show,
        ).pack(fill="x", pady=(2, 8), ipady=6)

    def _to_login(self):
        self._mode = "login"
        self._render()

    def _to_register(self):
        self._mode = "register"
        self._render()

    def _err(self, msg: str):
        self._lbl_err.config(text=msg)

    # ── Cadastro ────────────────────────────────────────────────────

    def _do_register(self):
        name  = self._name_var.get().strip()
        email = self._email_var.get().strip()
        pwd   = self._pass_var.get()
        pwd2  = self._pass2_var.get()

        if not all([name, email, pwd]):
            self._err("Preencha todos os campos")
            return
        if pwd != pwd2:
            self._err("As senhas não coincidem")
            return

        self._err("Conectando...")
        self.update()
        threading.Thread(
            target=self._register_thread, args=(name, email, pwd), daemon=True
        ).start()

    def _register_thread(self, name, email, pwd):
        import config
        from api import CactoAPI
        api = CactoAPI(config.get("backend_url"), "")
        result = api.register(name, email, pwd)
        self.after(0, lambda: self._on_register(result, name, email))

    def _on_register(self, result, name, email):
        if result is None:
            self._err("Erro ao criar conta. Tente novamente.")
        elif result.get("error") == "email_exists":
            self._err("Email já cadastrado")
        elif result.get("error") == "no_connection":
            self._err("Sem conexão com o servidor")
        else:
            import config
            d = config.load()
            d.update({
                "token":   result["token"],
                "user_id": result["user_id"],
                "name":    result.get("name", name),
                "email":   email,
            })
            config.save(d)
            self._success = True
            self.quit()

    # ── Login ────────────────────────────────────────────────────────

    def _do_login(self):
        email = self._email_var.get().strip()
        pwd   = self._pass_var.get()
        if not email or not pwd:
            self._err("Preencha todos os campos")
            return
        self._err("Conectando...")
        self.update()
        threading.Thread(
            target=self._login_thread, args=(email, pwd), daemon=True
        ).start()

    def _login_thread(self, email, pwd):
        import config
        from api import CactoAPI
        api = CactoAPI(config.get("backend_url"), "")
        result = api.login(email, pwd)
        self.after(0, lambda: self._on_login(result, email))

    def _on_login(self, result, email):
        if result is None:
            self._err("Erro ao entrar. Tente novamente.")
        elif result.get("error") == "invalid_credentials":
            self._err("Email ou senha incorretos")
        elif result.get("error") == "no_connection":
            self._err("Sem conexão com o servidor")
        else:
            import config
            d = config.load()
            d.update({
                "token":          result["token"],
                "user_id":        result["user_id"],
                "name":           result.get("name", ""),
                "email":          email,
                "streak_current": result.get("streak_current", 0),
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
