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
        print(f"[AUDIO] Arquivo não encontrado: {_ALARM_PATH}", flush=True)
        _play_beep()
        return

    def _tocar():
        # Sequência robusta: SEMPRE fecha o alias antes de reabrir. Sem isso,
        # a 2ª chamada falha ("device already open") e o som não toca de novo.
        with _mci_lock:
            mci = ctypes.windll.winmm.mciSendStringW
            mci("close cacto_alarm", None, 0, None)
            err = mci(f'open "{_ALARM_PATH}" type mpegvideo alias cacto_alarm',
                      None, 0, None)
            if err != 0:
                print(f"[AUDIO] MCI open error: {err}", flush=True)
                _play_fallback(_ALARM_PATH)
                return
            mci("play cacto_alarm", None, 0, None)  # sem wait — não bloqueia

    threading.Thread(target=_tocar, daemon=True).start()


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
