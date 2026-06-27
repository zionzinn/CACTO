import json
import os
from datetime import datetime

_QUEUE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offline_queue.json")


def _load() -> list:
    try:
        with open(_QUEUE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(queue: list):
    with open(_QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def enqueue(endpoint: str, body: dict):
    queue = _load()
    queue.append({
        "endpoint": endpoint,
        "body": body,
        "timestamp": datetime.utcnow().isoformat(),
    })
    _save(queue)


def flush(api) -> int:
    """Tenta reenviar eventos salvos offline. Retorna quantos foram enviados."""
    queue = _load()
    if not queue:
        return 0

    sent = 0
    remaining = []
    for item in queue:
        ep = item["endpoint"]
        body = item["body"]
        try:
            if ep == "/events/drink":
                result = api.event_drink(body["alarm_time"], body["response_time"])
            elif ep == "/events/empty":
                result = api.event_empty(body["alarm_time"], body["response_time"])
            elif ep == "/events/catchup":
                result = api.event_catchup(body["alarm_time"], body["response"])
            else:
                result = None

            if result is not None:
                sent += 1
            else:
                remaining.append(item)
        except Exception:
            remaining.append(item)

    _save(remaining)
    return sent


def count() -> int:
    return len(_load())
