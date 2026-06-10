from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import (
    CONTENT_SCHEDULER_TIMEZONE,
    EXPORT_SHEETS_API_KEY,
    EXPORT_SHEETS_BEARER_TOKEN,
    EXPORT_SHEETS_OAUTH_CLIENT_ID,
    EXPORT_SHEETS_OAUTH_CLIENT_SECRET,
    EXPORT_SHEETS_OAUTH_REFRESH_TOKEN,
    EXPORT_SHEETS_OAUTH_TOKEN_URL,
    EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL,
    EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY,
    EXPORT_SHEETS_SERVICE_ACCOUNT_TOKEN_URI,
    EXPORT_SHEETS_RANGE,
    EXPORT_SHEETS_SPREADSHEET_ID,
    EXPORT_SYNC_INTERVAL_MINUTES,
)
from app.db import get_users_for_export

logger = logging.getLogger(__name__)
_token_lock = threading.Lock()
_oauth_token_cache: dict[str, float | str] = {"access_token": "", "expires_at": 0.0}
_service_account_token_cache: dict[str, float | str] = {"access_token": "", "expires_at": 0.0}

EXPORT_COLUMNS = [
    "id",
    "telegram_id",
    "username",
    "created_at",
    "updated_at",
    "company",
    "contact_name",
    "contact_phone",
    "contact_email",
    "company_website",
    "simulate_consent",
    "valuation_consent",
    "last_connection_at",
    "accountants_count",
    "avg_salary",
    "express_saving_6",
    "express_saving_12",
    "meeting_booked",
    "advisory_band",
    "active_clients_count",
    "standardization_level",
    "automation_level",
    "precise_assessment",
    "margin_percent",
    "growth_band",
    "mna_interest",
    "file_downloaded",
    "uploaded_file_link",
    "valuation_revenue_mln",
    "valuation_share_percent",
    "valuation_profitability_percent",
    "valuation_profit_mln",
    "valuation_result_mln",
    "valuation_c1",
    "valuation_c2",
    "valuation_c3",
    "valuation_h",
    "valuation_q8_level",
    "valuation_auto_tools",
    "valuation_auto_other",
    "valuation_rfcomp",
    "valuation_new_result_mln",
    "support_program_registered",
    "business_stage",
]


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


def _format_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


def _build_values(rows: list[dict]) -> list[list[str]]:
    values: list[list[str]] = [EXPORT_COLUMNS]
    for row in rows:
        values.append([_format_cell(row.get(column)) for column in EXPORT_COLUMNS])
    return values


def _push_values_to_sheet(values: list[list[str]]):
    range_name = _normalize_sheet_range(EXPORT_SHEETS_RANGE)
    encoded_range = quote(range_name, safe="!:")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{EXPORT_SHEETS_SPREADSHEET_ID}"
        f"/values/{encoded_range}?valueInputOption=RAW"
    )
    auth_header = _build_auth_header()
    if not auth_header:
        url = f"{url}&key={EXPORT_SHEETS_API_KEY}"

    payload = json.dumps(
        {
            "range": range_name,
            "majorDimension": "ROWS",
            "values": values,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = Request(
        url=url,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            **({"Authorization": auth_header} if auth_header else {}),
        },
        method="PUT",
    )

    with urlopen(req, timeout=20) as response:
        response.read()


def _refresh_oauth_access_token() -> tuple[str, float]:
    payload = urlencode(
        {
            "client_id": EXPORT_SHEETS_OAUTH_CLIENT_ID,
            "client_secret": EXPORT_SHEETS_OAUTH_CLIENT_SECRET,
            "refresh_token": EXPORT_SHEETS_OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = Request(
        EXPORT_SHEETS_OAUTH_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
    access_token = str(body.get("access_token", "")).strip()
    expires_in = int(body.get("expires_in", 3600))
    if not access_token:
        raise RuntimeError(f"OAuth token refresh response does not contain access_token: {body}")
    expires_at = time.time() + max(expires_in - 60, 60)
    return access_token, expires_at


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_rs256(payload: bytes, private_key_pem: str) -> str:
    with NamedTemporaryFile("w", encoding="utf-8", delete=False) as key_file:
        key_file.write(private_key_pem)
        key_path = key_file.name
    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=payload,
            capture_output=True,
            check=True,
        )
        return _b64url(proc.stdout)
    finally:
        try:
            os.remove(key_path)
        except OSError:
            pass


def _refresh_service_account_access_token() -> tuple[str, float]:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL,
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "aud": EXPORT_SHEETS_SERVICE_ACCOUNT_TOKEN_URI,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = _sign_rs256(signing_input.encode("ascii"), EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY)
    assertion = f"{signing_input}.{signature}"
    payload = urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode("utf-8")
    req = Request(
        EXPORT_SHEETS_SERVICE_ACCOUNT_TOKEN_URI,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
    access_token = str(body.get("access_token", "")).strip()
    expires_in = int(body.get("expires_in", 3600))
    if not access_token:
        raise RuntimeError(f"Service account token response has no access_token: {body}")
    expires_at = time.time() + max(expires_in - 60, 60)
    return access_token, expires_at


def _get_service_account_access_token() -> str:
    if not (EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL and EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY):
        return ""
    with _token_lock:
        cached_token = str(_service_account_token_cache.get("access_token", ""))
        cached_expires_at = float(_service_account_token_cache.get("expires_at", 0.0))
        if cached_token and time.time() < cached_expires_at:
            return cached_token
        token, expires_at = _refresh_service_account_access_token()
        _service_account_token_cache["access_token"] = token
        _service_account_token_cache["expires_at"] = expires_at
        return token


def _get_oauth_access_token() -> str:
    if not (
        EXPORT_SHEETS_OAUTH_CLIENT_ID
        and EXPORT_SHEETS_OAUTH_CLIENT_SECRET
        and EXPORT_SHEETS_OAUTH_REFRESH_TOKEN
    ):
        return ""

    with _token_lock:
        cached_token = str(_oauth_token_cache.get("access_token", ""))
        cached_expires_at = float(_oauth_token_cache.get("expires_at", 0.0))
        if cached_token and time.time() < cached_expires_at:
            return cached_token

        try:
            token, expires_at = _refresh_oauth_access_token()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OAuth refresh token exchange failed (%s). "
                "Falling back to static bearer token or API key if configured.",
                exc,
            )
            _oauth_token_cache["access_token"] = ""
            _oauth_token_cache["expires_at"] = 0.0
            return ""
        _oauth_token_cache["access_token"] = token
        _oauth_token_cache["expires_at"] = expires_at
        return token


def _build_auth_header() -> str:
    service_account_access_token = _get_service_account_access_token()
    if service_account_access_token:
        return f"Bearer {service_account_access_token}"
    oauth_access_token = _get_oauth_access_token()
    if oauth_access_token:
        return f"Bearer {oauth_access_token}"
    if EXPORT_SHEETS_BEARER_TOKEN:
        return f"Bearer {EXPORT_SHEETS_BEARER_TOKEN}"
    return ""


async def sync_users_export():
    if not EXPORT_SHEETS_SPREADSHEET_ID:
        logger.info("Users export to sheets is disabled: missing export spreadsheet id.")
        return
    if not (
        EXPORT_SHEETS_API_KEY
        or EXPORT_SHEETS_BEARER_TOKEN
        or (EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL and EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY)
        or (
            EXPORT_SHEETS_OAUTH_CLIENT_ID
            and EXPORT_SHEETS_OAUTH_CLIENT_SECRET
            and EXPORT_SHEETS_OAUTH_REFRESH_TOKEN
        )
    ):
        logger.info(
            "Users export to sheets is disabled: provide API key, bearer token, or OAuth refresh credentials."
        )
        return

    try:
        if EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL and not EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY:
            logger.warning(
                "Service Account email is configured, but private key is empty. "
                "Set EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY."
            )
        if EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY and not EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL:
            logger.warning(
                "Service Account private key is configured, but email is empty. "
                "Set EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL."
            )
        if EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL and EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY:
            logger.info("Users export uses Service Account mode.")
        elif (
            EXPORT_SHEETS_OAUTH_CLIENT_ID
            and EXPORT_SHEETS_OAUTH_CLIENT_SECRET
            and EXPORT_SHEETS_OAUTH_REFRESH_TOKEN
        ):
            logger.info("Users export uses OAuth refresh-token mode (auto refresh enabled).")
        elif EXPORT_SHEETS_BEARER_TOKEN:
            logger.info("Users export uses static bearer token mode.")
        elif EXPORT_SHEETS_API_KEY:
            logger.info("Users export uses API key mode. If Google returns 401/403, configure OAuth refresh mode.")
        users = await get_users_for_export()
        values = _build_values(users)
        await asyncio.to_thread(_push_values_to_sheet, values)
        logger.info("Users export synced to sheets. Exported rows: %s", max(len(values) - 1, 0))
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            error_body = "<failed to decode error body>"
        logger.warning("Users export sync failed: %s; body=%s", exc, error_body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Users export sync failed: %s", exc)


def setup_export_scheduler(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        sync_users_export,
        trigger="interval",
        minutes=EXPORT_SYNC_INTERVAL_MINUTES,
        id="users_export_interval",
        coalesce=True,
        misfire_grace_time=120,
        replace_existing=True,
    )
    scheduler.add_job(
        sync_users_export,
        trigger="date",
        run_date=datetime.now(ZoneInfo(CONTENT_SCHEDULER_TIMEZONE)) + timedelta(seconds=20),
        id="users_export_startup",
        misfire_grace_time=120,
        replace_existing=True,
    )
