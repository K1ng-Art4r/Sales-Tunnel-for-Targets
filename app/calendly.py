import json
from dataclasses import dataclass
from datetime import date, datetime, time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.config import CALENDLY_API_TOKEN, CALENDLY_EVENT_TYPE_URI, MEETING_TIMEZONE


API_BASE = "https://api.calendly.com"
EVENT_TYPE_API_PREFIX = "https://api.calendly.com/event_types/"


class CalendlyNotConfiguredError(RuntimeError):
    pass


class CalendlyRequestError(RuntimeError):
    pass


@dataclass
class CalendlyBookingResult:
    booking_url: str
    cancel_url: str | None = None
    reschedule_url: str | None = None


def is_configured() -> bool:
    return bool(CALENDLY_API_TOKEN and CALENDLY_EVENT_TYPE_URI)


def _normalize_url(raw_url: str) -> str:
    value = raw_url.strip()
    if value.endswith("/"):
        value = value[:-1]
    if value.startswith("http://"):
        value = "https://" + value[len("http://"):]
    if not value.startswith("https://"):
        value = "https://" + value
    return value


def _headers() -> dict[str, str]:
    if not is_configured():
        raise CalendlyNotConfiguredError("Calendly credentials are not configured.")
    return {
        "Authorization": f"Bearer {CALENDLY_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AivelBot/1.0 (+https://aivel.ru)",
    }


def _request(method: str, path: str, *, query: dict | None = None, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, method=method, headers=_headers(), data=data)

    try:
        with urlopen(req, timeout=20) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        details = exc.read().decode("utf-8")
        if exc.code == 403 and "1010" in details:
            raise CalendlyRequestError(
                "Calendly вернул 403 (code 1010). Обычно это блокировка Cloudflare/WAF. "
                "Проверьте, что запрос идёт к api.calendly.com, у токена есть нужные scope, "
                "и попробуйте запрос с другого IP/VPN."
            ) from exc
        raise CalendlyRequestError(f"Calendly HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise CalendlyRequestError(f"Calendly connection error: {exc}") from exc


def _resolve_event_type() -> dict[str, str | list[str]]:
    if not CALENDLY_EVENT_TYPE_URI:
        raise CalendlyNotConfiguredError("CALENDLY_EVENT_TYPE_URI is missing.")

    raw_value = CALENDLY_EVENT_TYPE_URI.strip()
    if raw_value.startswith(EVENT_TYPE_API_PREFIX):
        return {"uri": raw_value, "location_kinds": []}

    normalized = _normalize_url(raw_value)
    if "calendly.com/" not in normalized:
        raise CalendlyRequestError(
            "CALENDLY_EVENT_TYPE_URI должен быть либо API URI event_type, "
            "либо публичной ссылкой Calendly вида https://calendly.com/username/event."
        )

    me_response = _request("GET", "/users/me")
    user_uri = me_response.get("resource", {}).get("uri")
    if not user_uri:
        raise CalendlyRequestError("Не удалось получить user URI из Calendly.")

    event_types_response = _request("GET", "/event_types", query={"user": user_uri})
    for item in event_types_response.get("collection", []):
        scheduling_url = item.get("scheduling_url")
        event_uri = item.get("uri")
        if not scheduling_url or not event_uri:
            continue
        if _normalize_url(scheduling_url) == normalized:
            locations = item.get("locations") or []
            location_kinds = []
            for location in locations:
                if isinstance(location, dict) and location.get("kind"):
                    location_kinds.append(location["kind"])
            return {"uri": event_uri, "location_kinds": location_kinds}

    raise CalendlyRequestError(
        "Не удалось сопоставить CALENDLY_EVENT_TYPE_URI с event type. "
        "Укажите API URI вида https://api.calendly.com/event_types/..."
    )


def get_available_hour_slots(target_date: date) -> list[datetime]:
    tz = ZoneInfo(MEETING_TIMEZONE)
    start_local = datetime.combine(target_date, time(9, 0), tzinfo=tz)
    end_local = datetime.combine(target_date, time(22, 0), tzinfo=tz)

    event_type_uri = str(_resolve_event_type()["uri"])
    response = _request(
        "GET",
        "/event_type_available_times",
        query={
            "event_type": event_type_uri,
            "start_time": start_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
            "end_time": end_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
        },
    )
    items = response.get("collection", [])

    slots: list[datetime] = []
    for item in items:
        start_time_raw = item.get("start_time")
        if not start_time_raw:
            continue
        start_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00")).astimezone(tz)
        if start_dt.minute == 0 and 9 <= start_dt.hour <= 21:
            slots.append(start_dt)

    slots.sort()
    unique_slots: list[datetime] = []
    seen = set()
    for slot in slots:
        key = slot.isoformat()
        if key not in seen:
            seen.add(key)
            unique_slots.append(slot)
    return unique_slots


def is_slot_available(slot_dt_local: datetime) -> bool:
    all_slots = get_available_hour_slots(slot_dt_local.date())
    target = slot_dt_local.replace(second=0, microsecond=0)
    return any(s.replace(second=0, microsecond=0) == target for s in all_slots)


def book_slot(slot_dt_local: datetime, invitee_name: str, invitee_email: str) -> CalendlyBookingResult:
    event_type = _resolve_event_type()
    event_type_uri = str(event_type["uri"])
    base_body = {
        "event_type": event_type_uri,
        "start_time": slot_dt_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
        "invitee": {
            "name": invitee_name,
            "email": invitee_email,
            "timezone": MEETING_TIMEZONE,
        },
    }

    response = _request("POST", "/invitees", body=base_body)

    resource = response.get("resource", {})
    return CalendlyBookingResult(
        booking_url=resource.get("scheduling_url", ""),
        cancel_url=resource.get("cancel_url"),
        reschedule_url=resource.get("reschedule_url"),
    )
