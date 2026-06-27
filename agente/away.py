import ctypes
import ctypes.wintypes
import threading
import time


class AwayDetector:
    """
    Detecta inatividade monitorando posição do cursor a cada 5s.
    Sem hooks de kernel — zero dependências externas.
    """

    def __init__(self, threshold_minutes: int = 8):
        self._threshold_secs = threshold_minutes * 60
        self._last_pos: tuple | None = None
        self._inactive_since: float = time.time()
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="AwayDetector")
        t.start()

    def stop(self):
        self._running = False

    def _get_cursor(self) -> tuple | None:
        pt = ctypes.wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
        return None

    def _loop(self):
        while self._running:
            pos = self._get_cursor()
            with self._lock:
                if pos is not None and pos != self._last_pos:
                    self._last_pos = pos
                    self._inactive_since = time.time()
            time.sleep(5)

    @property
    def is_away(self) -> bool:
        return self.seconds_inactive >= self._threshold_secs

    @property
    def seconds_inactive(self) -> int:
        with self._lock:
            return int(time.time() - self._inactive_since)

    def reset(self):
        with self._lock:
            self._inactive_since = time.time()
