"""
Playback de áudio via Windows MCI nativo.
Padrão idêntico ao D:\ÁGUA\agua_timer.py — sem pygame, sem dependências externas.
"""
import ctypes
import threading
import os

_mci_lock = threading.Lock()
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_ALARM_PATH = os.path.join(_ASSETS, "alarme.mp3")


def _mci(cmd: str):
    ctypes.windll.winmm.mciSendStringW(cmd, None, 0, None)


def _play_mci(path: str, alias: str):
    with _mci_lock:
        try:
            _mci(f'close {alias}')
            _mci(f'open "{path}" type mpegvideo alias {alias}')
            _mci(f'play {alias}')  # sem wait — não bloqueia a thread
        except Exception as e:
            print(f"[AUDIO] MCI erro ({alias}): {e}")
            _play_fallback(path)


def _stop_mci(alias: str):
    with _mci_lock:
        try:
            _mci(f'stop {alias}')
            _mci(f'close {alias}')
        except Exception:
            pass


def _play_fallback(path: str):
    """PowerShell WMP — igual ao agua_timer.py."""
    try:
        import subprocess
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             f'$m = New-Object -ComObject WMPlayer.OCX; $m.URL = "{path}"; $m.controls.play()'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[AUDIO] Fallback falhou: {e}")


def play_alarm():
    import config
    if not config.get("sound_enabled", True):
        return
    if not os.path.exists(_ALARM_PATH):
        print(f"[AUDIO] Arquivo não encontrado: {_ALARM_PATH}")
        _play_beep()
        return
    threading.Thread(
        target=_play_mci, args=(_ALARM_PATH, "cacto_alarm"), daemon=True
    ).start()


def stop_alarm():
    threading.Thread(target=_stop_mci, args=("cacto_alarm",), daemon=True).start()


def play_xp_sound():
    try:
        import winsound
        winsound.Beep(880, 120)
        winsound.Beep(1100, 120)
    except Exception:
        pass


def _play_beep():
    try:
        import winsound
        winsound.Beep(440, 500)
    except Exception:
        pass
