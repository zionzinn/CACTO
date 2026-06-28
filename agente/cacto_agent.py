#!/usr/bin/env python3
"""
CACTO — Agente Desktop v1.0.0
Entry point. Orquestra polling, heartbeat, popup, tray e away detection.
"""
import os
import sys
import threading
import time
import ctypes
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import tkinter as tk

import config
import audio
import local_queue as lq
from api import CactoAPI
from timer import GlobalTimer
from away import AwayDetector
from popup import PopupCentral
import painel as painel_module

AGENT_VERSION = config._DEFAULTS["agent_version"]


class CactoAgent:
    def __init__(self):
        self._api: CactoAPI | None = None
        self._timer = GlobalTimer()
        self._away  = AwayDetector(threshold_minutes=8)
        self._popup_open    = False
        self._paused_until: float | None = None   # pause local de pop-ups
        self._away_since:   float | None = None   # quando começou a ausência atual
        self._was_away      = False
        self._root: tk.Tk | None = None
        self._tray = None
        self._painel_win = None
        self._mutex = None  # Windows named mutex

    # ── Entry point ───────────────────────────────────────────────

    def run(self):
        config.load()

        if not self._acquire_lock():
            print("[CACTO] Já está rodando.")
            sys.exit(0)

        base_url = config.get("backend_url", "https://cacto-backend.onrender.com")
        token    = config.get("token", "")

        # Valida token existente; só mostra login se definitivamente inválido
        if token:
            me = CactoAPI(base_url, token).get_me()
            if me is not None and me.get("error") == "unauthorized":
                print("[CACTO] Token inválido — solicitando novo login.", flush=True)
                config.set("token", "")
                token = ""
            elif me and not me.get("error"):
                # Atualiza campos do perfil em cache
                d = config.load()
                d.update({
                    "name":           me.get("name", d.get("name", "")),
                    "streak_current": me.get("streak_current", d.get("streak_current", 0)),
                    "level":          me.get("level", d.get("level", 1)),
                    "xp_total":       me.get("xp_total", d.get("xp_total", 0)),
                })
                config.save(d)

        if not token:
            from register import RegisterWindow
            ok = RegisterWindow().show()
            if not ok:
                self._release_lock()
                sys.exit(0)
            config.load()
            token = config.get("token", "")

        self._api = CactoAPI(base_url, token)

        # Tk root oculto (master para janelas filhas)
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("CACTO")
        try:
            ico = os.path.join(_DIR, "assets", "cacto.ico")
            if os.path.exists(ico):
                self._root.iconbitmap(ico)
        except Exception:
            pass

        # Registro no Windows Startup
        self._setup_startup()

        # Away detector em thread daemon
        self._away.start()

        # Tray em thread daemon (run() bloqueia, por isso daemon)
        self._start_tray()

        # Polling e heartbeat em threads daemon
        threading.Thread(target=self._polling_loop,   daemon=True, name="Polling").start()
        threading.Thread(target=self._heartbeat_loop, daemon=True, name="Heartbeat").start()

        print(f"[CACTO] Agente v{AGENT_VERSION} iniciado.", flush=True)
        try:
            self._root.mainloop()
        finally:
            self._release_lock()

    # ── Single instance (Windows Named Mutex) ─────────────────────

    def _acquire_lock(self) -> bool:
        try:
            self._mutex = ctypes.windll.kernel32.CreateMutexW(
                None, True, "Global\\CactoAgent_SingleInstance"
            )
            err = ctypes.windll.kernel32.GetLastError()
            if err == 183:   # ERROR_ALREADY_EXISTS
                ctypes.windll.kernel32.CloseHandle(self._mutex)
                self._mutex = None
                return False
            return True
        except Exception:
            return True

    def _release_lock(self):
        if self._mutex:
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex)
            except Exception:
                pass

    # ── Windows Startup via Registry ──────────────────────────────

    def _setup_startup(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            cmd = f'"{sys.executable}" "{os.path.join(_DIR, "cacto_agent.py")}"'
            winreg.SetValueEx(key, "CACTO", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            print("[STARTUP] Registrado no Windows Startup.", flush=True)
        except Exception as e:
            print(f"[STARTUP] Não foi possível registrar: {e}", flush=True)

    # ── Tray ──────────────────────────────────────────────────────

    def _start_tray(self):
        from tray import CactoTray
        self._tray = CactoTray(self)
        threading.Thread(target=self._tray.start, daemon=True, name="Tray").start()

    def open_painel(self):
        if self._root:
            self._root.after(0, self._open_painel_main)

    def _open_painel_main(self):
        try:
            if self._painel_win and self._painel_win.winfo_exists():
                self._painel_win.lift()
                return
        except Exception:
            pass
        name = config.get("name", "")
        uid  = config.get("user_id", 0)
        self._painel_win = painel_module.show(self._root, self._api, name, uid)

    # ── Polling loop (a cada 10s) ─────────────────────────────────

    def _polling_loop(self):
        while True:
            try:
                self._poll_once()
            except Exception as e:
                print(f"[POLLING] Erro: {e}", flush=True)
            time.sleep(10)

    def _poll_once(self):
        session = self._api.get_session()
        if session is None:
            self._tray_update("offline", "CACTO 🌵 | Sem conexão")
            return

        self._timer.update(session)
        self._update_tray_from_timer()
        self._check_away_transition()

        if (self._timer.should_fire
                and not self._away.is_away
                and not self._popup_open
                and not self._is_paused_locally()):
            self._root.after(0, self._disparar_alarme)

    def _update_tray_from_timer(self):
        if not self._timer.is_active:
            self._tray_update("offline", "CACTO 🌵 | Aguardando sessão...")
            return
        if self._timer.is_paused:
            self._tray_update("paused", "CACTO 🌵 | Sessão pausada")
            return
        if self._away.is_away:
            self._tray_update("away", "CACTO 🌵 | Ausente")
            return

        secs = self._timer.seconds_until_next_alarm
        if secs is not None and secs > 0:
            m, s = divmod(secs, 60)
            tip = f"CACTO 🌵 | Próximo alarme em {m:02d}:{s:02d}"
        else:
            tip = "CACTO 🌵 | Alarme iminente!"
        self._tray_update("active", tip)

    def _tray_update(self, state: str, tooltip: str):
        if self._tray:
            self._tray.update_icon(state)
            self._tray.update_tooltip(tooltip)

    # ── Away detection / catch-up ─────────────────────────────────

    def _check_away_transition(self):
        now_away = self._away.is_away
        if now_away and not self._was_away:
            # Começou ausência
            self._away_since = time.time()
        elif not now_away and self._was_away and self._away_since is not None:
            # Voltou da ausência — calcula alarmes perdidos
            away_secs = time.time() - self._away_since
            self._away_since = None
            interval_secs = max(1, self._timer.interval_min * 60)
            perdidos = max(0, int(away_secs // interval_secs))
            alarm_time = datetime.utcnow().isoformat()
            self._root.after(0, lambda n=perdidos, at=alarm_time: self._check_catchup(n, at))
        self._was_away = now_away

    def _check_catchup(self, perdidos: int, alarm_time: str):
        if perdidos <= 0:
            return
        if perdidos <= 3:
            self._show_catchup(perdidos, alarm_time)
        else:
            # Ausência longa — registra silenciosamente
            threading.Thread(
                target=self._api.event_away, args=(alarm_time,), daemon=True
            ).start()

    def _show_catchup(self, perdidos: int, alarm_time: str):
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#0a1628")
        W, H = 340, 190
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        plural = "lembretes" if perdidos > 1 else "lembrete"
        tk.Label(
            win, fg="#aaaaaa", bg="#0a1628", wraplength=300,
            text=f"Você ficou ausente e perdeu {perdidos} {plural} de água.",
            font=("Segoe UI", 10),
        ).pack(pady=(20, 6))
        tk.Label(
            win, text="Bebeu água nesse período?",
            font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#0a1628",
        ).pack()

        bf = tk.Frame(win, bg="#0a1628")
        bf.pack(pady=12)

        def resp(r):
            win.destroy()
            threading.Thread(
                target=self._api.event_catchup, args=(alarm_time, r), daemon=True
            ).start()

        tk.Button(
            bf, text="✅ SIM", command=lambda: resp("catchup_yes"),
            bg="#00d4ff", fg="#0a1628",
            font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=8,
        ).pack(side="left", padx=10)
        tk.Button(
            bf, text="❌ NÃO", command=lambda: resp("catchup_no"),
            bg="#1a2a3a", fg="#aaaaaa",
            font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=8,
        ).pack(side="left", padx=10)

    # ── Heartbeat loop (a cada 30s) ───────────────────────────────

    def _heartbeat_loop(self):
        while True:
            time.sleep(30)
            try:
                result = self._api.heartbeat()
                if result:
                    self._timer.update(result)
                    sent = lq.flush(self._api)
                    if sent:
                        print(f"[QUEUE] {sent} evento(s) sincronizado(s).", flush=True)
                else:
                    if self._tray:
                        self._tray.notify("CACTO", "Sem conexão com o servidor")
            except Exception as e:
                print(f"[HEARTBEAT] Erro: {e}", flush=True)

    # ── Disparo do alarme ─────────────────────────────────────────

    def _disparar_alarme(self):
        if self._popup_open:
            return
        self._popup_open = True
        self._timer.alarm_fired()

        alarm_time = datetime.utcnow().isoformat()
        audio.play_alarm()

        streak = config.get("streak_current", 0)
        mult   = self._calc_mult(streak)

        popup = PopupCentral(
            master=self._root,
            alarm_time=alarm_time,
            streak=streak,
            xp_multiplier=mult,
            on_drink=lambda rt: self._on_drink(alarm_time, rt),
            on_empty=lambda rt: self._on_empty(alarm_time, rt),
            on_timeout=lambda: self._on_timeout(alarm_time),
            on_pause=self.pause_popups_local,
        )
        popup.show()

    def _on_drink(self, alarm_time: str, response_time: str):
        self._popup_open = False
        audio.stop_alarm()
        audio.play_xp_sound()
        result = self._api.event_drink(alarm_time, response_time)
        if result is None:
            lq.enqueue("/events/drink", {
                "alarm_time": alarm_time, "response_time": response_time
            })
        else:
            xp = result.get("xp_earned", 10)
            if self._tray:
                self._tray.notify("CACTO 💧", f"+{xp} XP! Bom trabalho!")
            print(f"[DRINK] +{xp} XP", flush=True)

    def _on_empty(self, alarm_time: str, response_time: str):
        self._popup_open = False
        audio.stop_alarm()
        result = self._api.event_empty(alarm_time, response_time)
        if result is None:
            lq.enqueue("/events/empty", {
                "alarm_time": alarm_time, "response_time": response_time
            })
        else:
            print(f"[EMPTY] +{result.get('xp_earned', 8)} XP", flush=True)

    def _on_timeout(self, alarm_time: str):
        self._popup_open = False
        audio.stop_alarm()
        threading.Thread(
            target=self._api.event_timeout, args=(alarm_time,), daemon=True
        ).start()

    # ── Pause local de pop-ups ────────────────────────────────────

    def _is_paused_locally(self) -> bool:
        if self._paused_until is None:
            return False
        if time.time() < self._paused_until:
            return True
        self._paused_until = None
        return False

    def pause_popups_local(self, minutes: int):
        self._paused_until = time.time() + minutes * 60
        print(f"[PAUSE] Pop-ups pausados localmente por {minutes}min.", flush=True)
        if self._tray:
            self._tray.notify("CACTO", f"Pop-ups pausados por {minutes} minutos")

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _calc_mult(streak: int) -> float:
        if streak >= 30: return 2.0
        if streak >= 7:  return 1.5
        if streak >= 3:  return 1.2
        return 1.0

    # ── Shutdown ──────────────────────────────────────────────────

    def shutdown(self):
        print("[CACTO] Encerrando...", flush=True)
        if config.get("is_admin", False):
            admin_key = config.get("admin_key", "")
            if admin_key and self._api:
                try:
                    self._api.session_end(admin_key)
                    print("[CACTO] Sessão encerrada (admin).", flush=True)
                except Exception:
                    pass
        self._away.stop()
        if self._tray:
            self._tray.stop()
        self._release_lock()
        if self._root:
            self._root.after(0, self._root.quit)


if __name__ == "__main__":
    CactoAgent().run()
