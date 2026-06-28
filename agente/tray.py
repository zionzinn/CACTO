"""System tray icon + menu direito usando pystray + Pillow."""
import os
import threading
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as Item, Menu

_ASSETS  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_ICO_PATH = os.path.join(_ASSETS, "cacto.ico")

_STATE_COLORS = {
    "active":  (0,   212, 100),
    "away":    (255, 200, 0),
    "paused":  (220, 50,  50),
    "offline": (100, 100, 100),
}


def _generate_icon(state: str) -> Image.Image:
    color = _STATE_COLORS.get(state, _STATE_COLORS["offline"])
    img = Image.new("RGBA", (32, 32), (10, 22, 40, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([5, 5, 27, 27], fill=(*color, 255))
    return img


def _ensure_ico():
    """Gera cacto.ico se não existir."""
    if os.path.exists(_ICO_PATH):
        return
    try:
        os.makedirs(_ASSETS, exist_ok=True)
        img = Image.new("RGBA", (32, 32), (10, 22, 40, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 28, 28], fill=(0, 212, 100, 255))
        # Anel ciano
        draw.ellipse([4, 4, 28, 28], outline=(0, 212, 255, 200), width=2)
        img.save(_ICO_PATH, format="ICO")
        print(f"[TRAY] Ícone gerado: {_ICO_PATH}")
    except Exception as e:
        print(f"[TRAY] Não foi possível gerar ícone: {e}")


def _load_icon(state: str) -> Image.Image:
    if state == "active":
        _ensure_ico()
        try:
            return Image.open(_ICO_PATH).convert("RGBA")
        except Exception:
            pass
    return _generate_icon(state)


class CactoTray:
    def __init__(self, agent):
        self._agent = agent
        self._icon: pystray.Icon | None = None
        self._state = "offline"

    # ── Menu ────────────────────────────────────────────────────────

    def _build_menu(self) -> Menu:
        import config
        is_admin  = config.get("is_admin", False)
        admin_key = config.get("token", "")   # ações admin usam o token como bearer

        # NB: pystray chama todo callback como action(icon, item) — os lambdas
        # PRECISAM aceitar (icon, item), senão estouram TypeError e o menu
        # inteiro fica "morto" (não responde ao clique).
        items = [
            Item("🌵 CACTO v1.0.0", None, enabled=False),
            Menu.SEPARATOR,
            # default=True → acionado no clique do ícone (duplo-clique no Windows)
            Item("Abrir painel", lambda icon, item: self._agent.open_painel(),
                 default=True),
            Menu.SEPARATOR,
        ]

        if is_admin:
            items += [
                Item("▶ Iniciar sessão",     lambda icon, item: self._do_admin("start",  admin_key)),
                Item("⏸ Pausar para todos", lambda icon, item: self._do_admin("pause",  admin_key)),
                Item("▶ Retomar para todos", lambda icon, item: self._do_admin("resume", admin_key)),
                Item("■ Encerrar sessão",    lambda icon, item: self._do_admin("end",    admin_key)),
                Menu.SEPARATOR,
            ]

        def _pause_item(label, minutes):
            return Item(label, lambda icon, item: self._agent.pause_popups_local(minutes))

        items += [
            Item("⏸ Pausar meus pop-ups", Menu(
                _pause_item("30 minutos", 30),
                _pause_item("1 hora",     60),
                _pause_item("Hoje",       480),
                _pause_item("Reunião",    90),
            )),
            Menu.SEPARATOR,
            Item("🔇 Silenciar som",  lambda icon, item: self._toggle_sound()),
            Menu.SEPARATOR,
            Item("✖ Fechar CACTO",   lambda icon, item: self._agent.shutdown()),
        ]

        return Menu(*items)

    def _do_admin(self, action: str, admin_key: str):
        api = self._agent._api
        fn  = {"start": api.session_start,
               "pause": api.session_pause,
               "resume": api.session_resume,
               "end":   api.session_end}.get(action)
        if fn:
            threading.Thread(target=fn, args=(admin_key,), daemon=True).start()

    def _toggle_sound(self):
        import config
        config.set("sound_enabled", not config.get("sound_enabled", True))

    # ── Controle público ────────────────────────────────────────────

    def start(self):
        _ensure_ico()
        img = _load_icon(self._state)
        self._icon = pystray.Icon(
            name="cacto",
            icon=img,
            title="CACTO 🌵 | Aguardando...",
            menu=self._build_menu(),
        )
        self._icon.run()   # bloqueia — chamar em thread daemon

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def update_icon(self, state: str):
        self._state = state
        if self._icon:
            try:
                self._icon.icon = _load_icon(state)
                self._icon.menu = self._build_menu()
            except Exception:
                pass

    def update_tooltip(self, text: str):
        if self._icon:
            try:
                self._icon.title = text
            except Exception:
                pass

    def notify(self, title: str, message: str):
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass
