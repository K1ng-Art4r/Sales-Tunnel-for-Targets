from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from urllib.request import urlopen


class EventsConfigError(RuntimeError):
    pass


class EventsRequestError(RuntimeError):
    pass


@dataclass
class EventItem:
    name: str
    time_and_date: str
    where: str
    support_text: str
    link: str
    calendly_link: str


def _normalize_header(value: str) -> str:
    normalized = value.strip().lower()
    lookalike_map = str.maketrans(
        {
            "а": "a",
            "е": "e",
            "о": "o",
            "р": "p",
            "с": "c",
            "у": "y",
            "к": "k",
            "х": "x",
            "м": "m",
            "т": "t",
            "в": "b",
            "н": "h",
        }
    )
    normalized = normalized.translate(lookalike_map)
    normalized = normalized.replace("&", "and")
    for char in (" ", "_", "-", "?", "(", ")", ":", "/", "#"):
        normalized = normalized.replace(char, "")
    return normalized


def _is_active(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"yes", "y", "да", "true", "1"}


def _extract_by_index(row: list[str], idx: int | None) -> str:
    if idx is None:
        return ""
    if idx < 0 or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def _first_present(mapping: dict[str, int], *keys: str) -> int | None:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def fetch_events(spreadsheet_id: str, api_key: str, sheet_range: str, timeout: int = 10) -> list[EventItem]:
    if not spreadsheet_id or not api_key:
        raise EventsConfigError("Google Sheets не настроен: добавьте GOOGLE_SHEETS_SPREADSHEET_ID и GOOGLE_SHEETS_API_KEY.")

    encoded_range = quote(sheet_range, safe="!:")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}"
        f"?key={api_key}&majorDimension=ROWS"
    )

    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise EventsRequestError(f"Не удалось загрузить мероприятия: {exc}") from exc

    rows = payload.get("values", [])
    if not rows:
        return []

    events: list[EventItem] = []

    normalized_headers = [_normalize_header(str(cell)) for cell in rows[0]]
    has_header = any(
        key in normalized_headers
        for key in ("name", "event", "мероприятие", "active", "show", "calendly", "calendlylink")
    )

    if has_header:
        header_map = {normalized: idx for idx, normalized in enumerate(normalized_headers)}

        name_idx = _first_present(header_map, "name", "event", "мероприятие", "название")
        time_idx = _first_present(header_map, "timeanddate", "timedate", "datetime", "date", "дата")
        where_idx = _first_present(header_map, "where", "location", "место")
        description_idx = _first_present(header_map, "supporttext", "description", "описание")
        link_idx = _first_present(header_map, "link", "url", "registrationlink", "eventlink", "linktoevent")
        active_idx = _first_present(header_map, "active", "show", "activeshow")
        calendly_idx = _first_present(
            header_map,
            "calendly",
            "calendlylink",
            "linktocalendly",
            "meetinglink",
            "календли",
            "ссылкакалендли",
        )

        for row in rows[1:]:
            if not row:
                continue

            if active_idx is not None and not _is_active(_extract_by_index(row, active_idx)):
                continue

            name = _extract_by_index(row, name_idx)
            if not name:
                continue

            events.append(
                EventItem(
                    name=name,
                    time_and_date=_extract_by_index(row, time_idx),
                    where=_extract_by_index(row, where_idx),
                    support_text=_extract_by_index(row, description_idx),
                    link=_extract_by_index(row, link_idx),
                    calendly_link=_extract_by_index(row, calendly_idx),
                )
            )
    else:
        # Legacy schema fallback: [id, name, time_and_date, where, support_text, link]
        for row in rows:
            if not row:
                continue

            values = list(row) + [""] * max(0, 6 - len(row))
            _, name, time_and_date, where, support_text, link = values[:6]
            if not str(name).strip():
                continue

            events.append(
                EventItem(
                    name=str(name).strip(),
                    time_and_date=str(time_and_date).strip(),
                    where=str(where).strip(),
                    support_text=str(support_text).strip(),
                    link=str(link).strip(),
                    calendly_link="",
                )
            )

    return events


def _format_date_header() -> str:
    now = datetime.now().strftime("%d.%m.%Y")
    return f"📅 <b>Где можно встретиться на мероприятиях</b>\n<i>Актуально на {now}</i>"


def format_events_message(events: list[EventItem]) -> str:
    if not events:
        return (
            "📅 <b>Где можно встретиться на мероприятиях</b>\n\n"
            "Сейчас в расписании пока нет событий. Загляните чуть позже."
        )

    lines = [_format_date_header(), "", "Подобрали актуальные события:"]
    for idx, event in enumerate(events, start=1):
        lines.extend(
            [
                "",
                f"<b>{idx}. {html.escape(event.name)}</b>",
                f"🗓 <b>Дата:</b> {html.escape(event.time_and_date) or 'Уточняется'}",
                f"📍 <b>Формат/место:</b> {html.escape(event.where) or 'Уточняется'}",
            ]
        )

        if event.support_text:
            lines.append(f"📝 <b>Описание:</b> {html.escape(event.support_text)}")
        if event.link:
            safe_link = html.escape(event.link, quote=True)
            lines.append(f"🔗 <a href=\"{safe_link}\">Регистрация / детали</a>")
        if event.calendly_link:
            safe_calendly = html.escape(event.calendly_link, quote=True)
            lines.append(
                f"🤝 <a href=\"{safe_calendly}\">Запись на личную встречу на этом мероприятии (Calendly)</a>"
            )

    lines.extend(["", "📌 Если хотите, подскажу, на какое событие лучше идти первым."])
    return "\n".join(lines)
