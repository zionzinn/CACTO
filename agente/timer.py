"""
Timer baseado em CICLOS.

Em vez de confiar no next_alarm_at deslizante do servidor (que muda a cada
poll e nunca estabiliza em zero), calculamos localmente quantos ciclos
completos de `interval_sec` já se passaram desde `session_start`. Cada ciclo
dispara no máximo uma vez (_last_fired_cycle). Robusto a polls perdidos e a
servidor lento.

Baseline: ao ver um session_start novo, fixamos _last_fired_cycle no ciclo já
decorrido — assim NÃO disparamos no instante em que a sessão inicia (ciclo 0,
ainda em contagem), nem ao reconectar no meio de um ciclo. O primeiro disparo
acontece quando o primeiro intervalo COMPLETA (vira ciclo 1).
"""
from datetime import datetime, timezone
import threading


class GlobalTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._session_start = None
        self._baseline_start = None    # start contra o qual já fizemos baseline
        self._interval_sec = 25 * 60
        self._is_active = False
        self._is_paused = False
        self._paused_elapsed = 0.0
        self._last_fired_cycle = 0

    def update(self, session_data: dict):
        with self._lock:
            self._is_active = bool(session_data.get("is_active", False))
            self._is_paused = bool(session_data.get("is_paused", False))
            self._interval_sec = max(1, int(session_data.get("interval_min", 25)) * 60)
            self._paused_elapsed = float(session_data.get("paused_elapsed") or 0)

            new_start = None
            start_str = session_data.get("session_start")
            if start_str:
                # suporta com e sem timezone
                start_str = start_str.replace("Z", "+00:00")
                try:
                    new_start = datetime.fromisoformat(start_str)
                    if new_start.tzinfo is None:
                        new_start = new_start.replace(tzinfo=timezone.utc)
                except Exception as e:
                    print(f"[TIMER] erro parse session_start: {e}", flush=True)
                    new_start = None

            self._session_start = new_start
            # Só rebaseline quando vemos um start NOVO e válido (sessão nova).
            # Um blip de rede (start=None por um poll) NÃO reseta o histórico —
            # quando a sessão volta com o mesmo start, preservamos o ciclo já
            # disparado e não perdemos/duplicamos alarme.
            if new_start is not None and new_start != self._baseline_start:
                self._baseline_start = new_start
                self._last_fired_cycle = self._cycle()

    def _elapsed(self) -> float:
        """Segundos decorridos desde o início da sessão, descontando pausas."""
        if not self._session_start:
            return 0.0
        now = datetime.now(timezone.utc)
        total = (now - self._session_start).total_seconds()
        return max(0.0, total - self._paused_elapsed)

    def _cycle(self) -> int:
        """Ciclo atual (sem lock — chamador deve segurar self._lock)."""
        if not self._session_start:
            return 0
        return int(self._elapsed() / self._interval_sec)

    @property
    def current_cycle(self) -> int:
        """Qual ciclo completo estamos (0 = ainda no primeiro intervalo)."""
        with self._lock:
            if not self._is_active or not self._session_start:
                return -1
            return self._cycle()

    @property
    def seconds_until_next(self) -> int | None:
        """Segundos até o próximo alarme. None se inativo/pausado."""
        with self._lock:
            if not self._is_active or self._is_paused or not self._session_start:
                return None
            elapsed = self._elapsed()
            remaining = self._interval_sec - (elapsed % self._interval_sec)
            return max(0, int(remaining))

    @property
    def should_fire(self) -> bool:
        """True quando um ciclo completou e ainda não disparamos para ele."""
        with self._lock:
            if not self._is_active or self._is_paused or not self._session_start:
                return False
            return self._cycle() > self._last_fired_cycle

    def alarm_fired(self):
        """Marcar que o ciclo atual já foi disparado."""
        with self._lock:
            cycle = self._cycle()
            self._last_fired_cycle = cycle
            print(f"[TIMER] Alarme disparado. Ciclo {cycle} marcado. "
                  f"Próximo em ~{self._interval_sec}s", flush=True)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def interval_sec(self) -> int:
        return self._interval_sec
