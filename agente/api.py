"""Todas as chamadas HTTP ao backend CACTO."""
import requests

TIMEOUT = 8


class CactoAPI:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self, admin_key: str = None) -> dict:
        key = admin_key if admin_key else self.token
        return {"Authorization": f"Bearer {key}"}

    def _get(self, path: str, params: dict = None) -> dict | None:
        try:
            r = requests.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params,
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def _post(self, path: str, body: dict = None, admin_key: str = None) -> dict | None:
        try:
            r = requests.post(
                f"{self.base_url}{path}",
                json=body or {},
                headers=self._headers(admin_key),
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    # ── Auth ──────────────────────────────────────────────────────────

    def register(self, name: str, email: str, password: str) -> dict | None:
        try:
            r = requests.post(
                f"{self.base_url}/register",
                json={"name": name, "email": email, "password": password},
                timeout=TIMEOUT,
            )
            if r.status_code == 409:
                return {"error": "email_exists"}
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return {"error": "no_connection"}
        except Exception:
            return None

    def login(self, email: str, password: str) -> dict | None:
        try:
            r = requests.post(
                f"{self.base_url}/login",
                json={"email": email, "password": password},
                timeout=TIMEOUT,
            )
            if r.status_code == 401:
                return {"error": "invalid_credentials"}
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return {"error": "no_connection"}
        except Exception:
            return None

    def get_me(self) -> dict | None:
        try:
            r = requests.get(f"{self.base_url}/me", headers=self._headers(), timeout=TIMEOUT)
            if r.status_code == 401:
                return {"error": "unauthorized"}
            r.raise_for_status()
            return r.json()
        except Exception:
            return None  # connection failed — token still assumed valid

    # ── Sessão ────────────────────────────────────────────────────────

    def get_session(self) -> dict | None:
        return self._get("/session")

    def session_start(self, admin_key: str) -> dict | None:
        return self._post("/session/start", admin_key=admin_key)

    def session_pause(self, admin_key: str) -> dict | None:
        return self._post("/session/pause", admin_key=admin_key)

    def session_resume(self, admin_key: str) -> dict | None:
        return self._post("/session/resume", admin_key=admin_key)

    def session_end(self, admin_key: str) -> dict | None:
        return self._post("/session/end", admin_key=admin_key)

    # ── Eventos ───────────────────────────────────────────────────────

    def event_drink(self, alarm_time: str, response_time: str) -> dict | None:
        return self._post("/events/drink", {
            "alarm_time": alarm_time,
            "response_time": response_time,
        })

    def event_empty(self, alarm_time: str, response_time: str) -> dict | None:
        return self._post("/events/empty", {
            "alarm_time": alarm_time,
            "response_time": response_time,
        })

    def event_timeout(self, alarm_time: str) -> dict | None:
        return self._post("/events/timeout", {"alarm_time": alarm_time})

    def event_away(self, alarm_time: str) -> dict | None:
        return self._post("/events/away", {"alarm_time": alarm_time})

    def event_catchup(self, alarm_time: str, response: str) -> dict | None:
        return self._post("/events/catchup", {
            "alarm_time": alarm_time,
            "response": response,
        })

    def heartbeat(self) -> dict | None:
        import config
        return self._post("/heartbeat", {
            "agent_version": config.get("agent_version", "1.0.0"),
        })

    # ── Stats ─────────────────────────────────────────────────────────

    def get_ranking(self, period: str = "day") -> list | None:
        result = self._get("/stats/ranking", params={"period": period})
        if isinstance(result, list):
            return result
        return None

    def get_my_stats(self) -> dict | None:
        return self._get("/stats/me")

    def get_team_stats(self) -> dict | None:
        return self._get("/stats/team")

    def get_online(self) -> list | None:
        result = self._get("/admin/online")
        return result if isinstance(result, list) else None
