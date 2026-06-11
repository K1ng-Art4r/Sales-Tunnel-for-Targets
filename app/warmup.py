from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import (
    CONTENT_SCHEDULER_TIMEZONE,
    CONTENT_SHEETS_API_KEY,
    CONTENT_SHEETS_RANGE,
    CONTENT_SHEETS_SPREADSHEET_ID,
)
from app.db import add_event, get_all_users_for_push, log_push_delivery, was_push_sent

logger = logging.getLogger(__name__)
WELCOME_POST_DELAY_MINUTES = 1  # send POST-001 one minute after registration
WELCOME_POST_CHECK_INTERVAL_MINUTES = 1
LOG_PREVIEW_LIMIT = 120
TIMEZONE_ALIASES = {
    "moscow": "Europe/Moscow",
    "msk": "Europe/Moscow",
    "europe/moscow": "Europe/Moscow",
    "utc+3": "Europe/Moscow",
    "gmt+3": "Europe/Moscow",
}


@dataclass
class PushPost:
    post_id: str
    title: str
    text: str
    cta: str
    link: str
    media: str
    send_at: datetime | None


def _preview(value: str | None, limit: int = LOG_PREVIEW_LIMIT) -> str:
    if not value:
        return ""

    normalized = " ".join(str(value).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _format_post_for_log(post: PushPost) -> dict[str, str | bool]:
    return {
        "post_id": post.post_id,
        "title": _preview(post.title),
        "text": _preview(post.text),
        "cta": _preview(post.cta),
        "has_link": bool(post.link),
        "has_media": bool(post.media),
        "send_at": post.send_at.isoformat() if post.send_at else "",
    }


def _normalize_header(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("&", "and")
    for char in (" ", "_", "-", "?", "(", ")", ":", "/", "."):
        normalized = normalized.replace(char, "")
    return normalized


def _first_present(mapping: dict[str, int], *keys: str) -> int | None:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _extract_by_index(row: list[str], idx: int | None) -> str:
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def _normalize_sheet_range(sheet_range: str) -> str:
    if "!" not in sheet_range:
        return sheet_range
    sheet_name, cell_range = sheet_range.split("!", 1)
    stripped = sheet_name.strip()
    if stripped.startswith("'") and stripped.endswith("'"):
        return sheet_range

    has_special_chars = any(not char.isascii() or char in {" ", "-"} for char in stripped)
    if has_special_chars:
        return f"'{stripped}'!{cell_range}"
    return sheet_range


def _parse_send_at(date_raw: str, time_raw: str, tz_name: str) -> datetime | None:
    if not date_raw:
        return None

    date_value = date_raw.strip()
    time_value = time_raw.strip().replace("\u202f", " ").replace("\xa0", " ")
    dt_value = " ".join(part for part in (date_value, time_value) if part).strip()
    resolved_tz = _resolve_timezone(tz_name)
    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %I:%M:%S %p",
        "%d.%m.%Y %I:%M %p",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(dt_value, fmt)
            send_at = parsed.replace(tzinfo=resolved_tz)
            logger.info(
                "Push post date parsed: date=%r time=%r timezone=%s format=%s send_at=%s",
                date_raw,
                time_raw,
                resolved_tz.key,
                fmt,
                send_at.isoformat(),
            )
            return send_at
        except ValueError:
            continue

    logger.warning("Could not parse push post date/time: date=%r time=%r timezone=%r", date_raw, time_raw, tz_name)
    return None


def _resolve_timezone(tz_name: str | None) -> ZoneInfo:
    raw = (tz_name or "").strip()
    normalized_key = raw.casefold().replace(" ", "")
    alias = TIMEZONE_ALIASES.get(normalized_key, raw)

    candidates = [
        alias,
        raw,
        CONTENT_SCHEDULER_TIMEZONE,
        "Europe/Moscow",
        "UTC",
    ]

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return ZoneInfo(candidate)
        except ZoneInfoNotFoundError:
            continue

    logger.warning("No valid timezone found for '%s'. Falling back to UTC.", tz_name)
    return ZoneInfo("UTC")


def _build_text(post: PushPost) -> str:
    lines = []
    if post.title:
        lines.append(f"<b>{post.title}</b>")
    if post.text:
        lines.append(post.text)
    return "\n\n".join(lines).strip() or " "


def _build_keyboard(post: PushPost) -> InlineKeyboardMarkup | None:
    if not post.cta:
        return None

    if post.post_id.upper() == "POST-001":
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=post.cta, callback_data="tool:simulate")]]
        )

    if post.link:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=post.cta, url=post.link)]]
        )

    return None


def fetch_push_posts() -> list[PushPost]:
    spreadsheet_id = CONTENT_SHEETS_SPREADSHEET_ID
    api_key = CONTENT_SHEETS_API_KEY
    sheet_range = _normalize_sheet_range(CONTENT_SHEETS_RANGE)

    logger.info(
        "Push content fetch started: spreadsheet_configured=%s api_key_configured=%s range=%r",
        bool(spreadsheet_id),
        bool(api_key),
        sheet_range,
    )

    if not spreadsheet_id or not api_key:
        logger.warning("Push content sheets are not configured.")
        return []

    encoded_range = quote(sheet_range, safe="!:")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}"
        f"?key={api_key}&majorDimension=ROWS"
    )

    try:
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch push content (range=%s): %s", sheet_range, exc)
        return []

    rows = payload.get("values", [])
    logger.info("Push content fetch completed: rows_received=%s range=%r", len(rows), sheet_range)
    if len(rows) < 2:
        logger.warning("Push content has no data rows: rows_received=%s range=%r", len(rows), sheet_range)
        return []

    raw_headers = [str(cell) for cell in rows[0]]
    header_map = {_normalize_header(cell): idx for idx, cell in enumerate(raw_headers)}
    logger.info("Push content headers: raw=%s normalized=%s", raw_headers, header_map)

    id_idx = _first_present(header_map, "id")
    date_idx = _first_present(header_map, "date", "дата")
    time_idx = _first_present(header_map, "time", "время")
    timezone_idx = _first_present(header_map, "timezone", "часовойпояс")
    title_idx = _first_present(header_map, "title", "заголовок")
    text_idx = _first_present(header_map, "message", "текстсообщения", "text", "body")
    cta_idx = _first_present(header_map, "cta")
    link_idx = _first_present(header_map, "link", "ссылка", "url")
    media_idx = _first_present(header_map, "media", "медиа")
    logger.info(
        "Push content column mapping: id=%s date=%s time=%s timezone=%s title=%s text=%s cta=%s link=%s media=%s",
        id_idx,
        date_idx,
        time_idx,
        timezone_idx,
        title_idx,
        text_idx,
        cta_idx,
        link_idx,
        media_idx,
    )

    if id_idx is None:
        logger.warning("Push content ID column was not found. No posts can be parsed.")

    posts: list[PushPost] = []
    skipped_without_id = 0
    for row_number, row in enumerate(rows[1:], start=2):
        logger.info("Push content row received: row=%s cells=%s", row_number, [_preview(str(cell)) for cell in row])
        post_id = _extract_by_index(row, id_idx)
        if not post_id:
            skipped_without_id += 1
            logger.info("Push content row skipped without post id: row=%s", row_number)
            continue

        date_raw = _extract_by_index(row, date_idx)
        time_raw = _extract_by_index(row, time_idx)
        tz_name = _extract_by_index(row, timezone_idx) or CONTENT_SCHEDULER_TIMEZONE
        send_at = _parse_send_at(date_raw, time_raw, tz_name)

        post = PushPost(
            post_id=post_id.strip(),
            title=_extract_by_index(row, title_idx),
            text=_extract_by_index(row, text_idx),
            cta=_extract_by_index(row, cta_idx),
            link=_extract_by_index(row, link_idx),
            media=_extract_by_index(row, media_idx),
            send_at=send_at,
        )
        posts.append(post)
        logger.info(
            "Push content post parsed: row=%s date_raw=%r time_raw=%r timezone_raw=%r post=%s",
            row_number,
            date_raw,
            time_raw,
            tz_name,
            _format_post_for_log(post),
        )

    logger.info("Push content parsing finished: parsed_posts=%s skipped_without_id=%s", len(posts), skipped_without_id)
    return posts


async def _send_post_to_user(bot: Bot, user: dict, post: PushPost):
    user_id = int(user["id"])
    telegram_id = user["telegram_id"]
    if await was_push_sent(user_id, post.post_id):
        logger.info("Push post already delivered, skipping: user_id=%s post_id=%s", user_id, post.post_id)
        return

    keyboard = _build_keyboard(post)
    text = _build_text(post)
    delivery_mode = "photo" if post.media else "message"
    logger.info(
        "Push post send attempt: user_id=%s telegram_id=%s mode=%s post=%s text_preview=%r has_keyboard=%s",
        user_id,
        telegram_id,
        delivery_mode,
        _format_post_for_log(post),
        _preview(text),
        keyboard is not None,
    )

    try:
        if post.media:
            await bot.send_photo(
                chat_id=telegram_id,
                photo=post.media,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        await log_push_delivery(user_id, post.post_id)
        await add_event(user_id, "push_post_sent", post.post_id)
        logger.info("Push post delivered and logged: user_id=%s telegram_id=%s post_id=%s", user_id, telegram_id, post.post_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send post %s to %s: %s", post.post_id, telegram_id, exc)


async def send_scheduled_post(bot: Bot, post: PushPost):
    users = await get_all_users_for_push()
    logger.info("Scheduled push post started: post=%s users_count=%s", _format_post_for_log(post), len(users))
    for user in users:
        await _send_post_to_user(bot, user, post)
    logger.info("Scheduled push post finished: post_id=%s users_count=%s", post.post_id, len(users))


async def send_welcome_post(bot: Bot):
    logger.info("Welcome push scan started.")
    posts = await asyncio.to_thread(fetch_push_posts)
    welcome = next((post for post in posts if post.post_id.upper() == "POST-001"), None)
    if not welcome:
        logger.info("Welcome post POST-001 not found in push content. parsed_posts=%s", len(posts))
        return

    logger.info("Welcome post found: post=%s", _format_post_for_log(welcome))
    users = await get_all_users_for_push()
    scheduler_tz = _resolve_timezone(CONTENT_SCHEDULER_TIMEZONE)
    now = datetime.now(scheduler_tz)
    checked_users = 0
    eligible_users = 0
    skipped_without_created_at = 0
    skipped_too_new = 0
    for user in users:
        created_at = user.get("created_at")
        if not created_at:
            skipped_without_created_at += 1
            logger.info("Welcome push user skipped without created_at: user_id=%s", user.get("id"))
            continue
        checked_users += 1
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=scheduler_tz)
        created_local = created_at.astimezone(scheduler_tz)
        eligible_at = created_local + timedelta(minutes=WELCOME_POST_DELAY_MINUTES)
        if now >= eligible_at:
            eligible_users += 1
            await _send_post_to_user(bot, user, welcome)
        else:
            skipped_too_new += 1
            logger.info(
                "Welcome push user is not eligible yet: user_id=%s created_at=%s eligible_at=%s now=%s",
                user.get("id"),
                created_local.isoformat(),
                eligible_at.isoformat(),
                now.isoformat(),
            )
    logger.info(
        "Welcome scan completed. users_total=%s checked_users=%s eligible_users=%s skipped_without_created_at=%s skipped_too_new=%s delay_min=%s",
        len(users),
        checked_users,
        eligible_users,
        skipped_without_created_at,
        skipped_too_new,
        WELCOME_POST_DELAY_MINUTES,
    )


async def refresh_week_schedule(bot: Bot, scheduler: AsyncIOScheduler):
    logger.info("Push schedule refresh started.")
    posts = await asyncio.to_thread(fetch_push_posts)
    scheduler_tz = _resolve_timezone(CONTENT_SCHEDULER_TIMEZONE)
    now = datetime.now(scheduler_tz)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    logger.info(
        "Push schedule refresh context: posts_count=%s timezone=%s now=%s week_start=%s week_end=%s",
        len(posts),
        scheduler_tz.key,
        now.isoformat(),
        week_start.isoformat(),
        week_end.isoformat(),
    )

    removed_jobs = 0
    for job in scheduler.get_jobs():
        if job.id.startswith("push:"):
            scheduler.remove_job(job.id)
            removed_jobs += 1
    logger.info("Push schedule old jobs removed: count=%s", removed_jobs)

    scheduled_count = 0
    skipped_welcome = 0
    skipped_without_send_at = 0
    skipped_outside_window = 0
    for post in posts:
        if post.post_id.upper() == "POST-001":
            skipped_welcome += 1
            logger.info("Push schedule post skipped because it is welcome post: post=%s", _format_post_for_log(post))
            continue
        if not post.send_at:
            skipped_without_send_at += 1
            logger.warning("Push schedule post skipped without send_at: post=%s", _format_post_for_log(post))
            continue
        send_at = post.send_at.astimezone(scheduler_tz)
        if send_at < now or send_at < week_start or send_at >= week_end:
            skipped_outside_window += 1
            logger.info(
                "Push schedule post skipped outside active window: post=%s send_at=%s now=%s week_start=%s week_end=%s",
                _format_post_for_log(post),
                send_at.isoformat(),
                now.isoformat(),
                week_start.isoformat(),
                week_end.isoformat(),
            )
            continue

        scheduler.add_job(
            send_scheduled_post,
            trigger="date",
            run_date=send_at,
            kwargs={"bot": bot, "post": post},
            id=f"push:{post.post_id}:{send_at.isoformat()}",
            replace_existing=True,
        )
        scheduled_count += 1
        logger.info("Push schedule post scheduled: post=%s send_at=%s", _format_post_for_log(post), send_at.isoformat())

    logger.info(
        "Push schedule refreshed. scheduled=%s skipped_welcome=%s skipped_without_send_at=%s skipped_outside_window=%s",
        scheduled_count,
        skipped_welcome,
        skipped_without_send_at,
        skipped_outside_window,
    )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler_tz = _resolve_timezone(CONTENT_SCHEDULER_TIMEZONE)
    logger.info("Push scheduler setup started: timezone=%s", scheduler_tz.key)
    scheduler = AsyncIOScheduler(timezone=scheduler_tz)

    scheduler.add_job(
        refresh_week_schedule,
        trigger="cron",
        hour=0,
        minute=0,
        kwargs={"bot": bot, "scheduler": scheduler},
        id="push_refresh_week_schedule",
        replace_existing=True,
    )
    scheduler.add_job(
        send_welcome_post,
        trigger="interval",
        minutes=WELCOME_POST_CHECK_INTERVAL_MINUTES,
        kwargs={"bot": bot},
        id="push_welcome_post_interval",
        replace_existing=True,
    )
    scheduler.add_job(
        send_welcome_post,
        trigger="date",
        run_date=datetime.now(scheduler_tz) + timedelta(seconds=10),
        kwargs={"bot": bot},
        id="push_welcome_post_startup",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_week_schedule,
        trigger="date",
        run_date=datetime.now(scheduler_tz) + timedelta(seconds=10),
        kwargs={"bot": bot, "scheduler": scheduler},
        id="push_refresh_startup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Push scheduler started: jobs=%s", [job.id for job in scheduler.get_jobs()])
    return scheduler
