import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

_DEFAULTS = {
    "token": "",
    "user_id": None,
    "name": "",
    "email": "",
    "is_admin": False,
    "admin_key": "",
    "popup_mode": "central",
    "monitor": 0,
    "sound_enabled": True,
    "backend_url": "https://cacto-backend.onrender.com",
    "agent_version": "1.0.0",
    "offline_queue_path": "offline_queue.json",
    "streak_current": 0,
}

_data: dict = {}


def load() -> dict:
    global _data
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        _data = {**_DEFAULTS, **saved}
    except (FileNotFoundError, json.JSONDecodeError):
        _data = dict(_DEFAULTS)
    return _data


def save(data: dict):
    global _data
    _data = data
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2, ensure_ascii=False)


def is_registered() -> bool:
    return bool(load().get("token"))


def get(key, default=None):
    return load().get(key, default)


def set(key, value):
    d = load()
    d[key] = value
    save(d)
