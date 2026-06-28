from datetime import datetime
from typing import Optional


class GlobalTimer:
    """
    Calcula o estado do timer a partir dos dados do servidor.
    O relógio é do servidor — next_alarm_at é a referência.
    """

    def __init__(self):
        self._session: dict = {}
        self._next_alarm_at: Optional[str] = None
        self._last_fired_alarm_at: Optional[str] = None

    def update(self, session_data: dict):
        self._session = session_data or {}
        self._next_alarm_at = self._session.get("next_alarm_at")

    @property
    def is_active(self) -> bool:
        return bool(self._session.get("is_active"))

    @property
    def is_paused(self) -> bool:
        return bool(self._session.get("is_paused"))

    @property
    def interval_min(self) -> int:
        return int(self._session.get("interval_min") or 25)

    @property
    def next_alarm_at(self) -> Optional[str]:
        return self._next_alarm_at

    @property
    def seconds_until_next_alarm(self) -> Optional[int]:
        if not self.is_active or self.is_paused:
            return None
        naa = self._next_alarm_at
        if not naa:
            return None
        try:
            diff = (datetime.fromisoformat(naa) - datetime.utcnow()).total_seconds()
            # Diferença absurda (> 2h): relógio local provavelmente errado
            if abs(diff) > 7200:
                return None
            return int(diff)
        except Exception:
            return None

    @property
    def should_fire(self) -> bool:
        if not self.is_active or self.is_paused:
            return False
        naa = self._next_alarm_at
        if not naa:
            return False
        secs = self.seconds_until_next_alarm
        if secs is None:
            return False
        # Dispara quando zerou E ainda não disparamos ESTE alarme.
        # Quando o servidor manda um next_alarm_at novo (diferente do último
        # disparado), volta a disparar normalmente — nunca trava.
        return secs <= 0 and naa != self._last_fired_alarm_at

    def alarm_fired(self):
        """Registra o alarme que acabou de disparar. Evita double-fire do MESMO."""
        self._last_fired_alarm_at = self._next_alarm_at

    def debug(self) -> str:
        return (f"next={self._next_alarm_at} "
                f"last_fired={self._last_fired_alarm_at} "
                f"secs={self.seconds_until_next_alarm} "
                f"should_fire={self.should_fire}")
