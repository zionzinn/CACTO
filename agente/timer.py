from datetime import datetime
from typing import Optional


class GlobalTimer:
    """
    Calcula o estado do timer a partir dos dados do servidor.
    O relógio é do servidor — next_alarm_at é a referência.
    """

    def __init__(self):
        self._session: dict = {}
        self._last_fired_alarm: Optional[str] = None

    def update(self, session_data: dict):
        self._session = session_data or {}

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
        return self._session.get("next_alarm_at")

    @property
    def seconds_until_next_alarm(self) -> Optional[int]:
        if not self.is_active or self.is_paused:
            return None
        naa = self.next_alarm_at
        if not naa:
            return None
        try:
            target = datetime.fromisoformat(naa)
            now = datetime.utcnow()
            diff = (target - now).total_seconds()
            # Diferença absurda (> 2h): relógio local provavelmente errado
            if abs(diff) > 7200:
                return None
            return int(diff)
        except Exception:
            return None

    @property
    def should_fire(self) -> bool:
        secs = self.seconds_until_next_alarm
        if secs is None:
            return False
        naa = self.next_alarm_at
        if naa is None:
            return False
        if self._last_fired_alarm == naa:
            return False
        return secs <= 0

    def alarm_fired(self):
        """Registra que o alarme atual disparou. Evita double-fire."""
        self._last_fired_alarm = self.next_alarm_at
