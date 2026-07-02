import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


ALLOWED_PROFILE_FIELDS = {
    "company",
    "company_website",
    "simulate_consent",
    "valuation_consent",
}
ALLOWED_FUNNEL_FIELDS = {
    "last_connection_at",
    "contact_name",
    "contact_phone",
    "contact_email",
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
}
ALLOWED_STANDARDIZATION = {"high", "medium", "low"}
ALLOWED_AUTOMATION = {"none", "partial", "systems"}
ALLOWED_ADVISORY = {"lt10", "10_20", "gt20"}
ALLOWED_GROWTH = {"none", "normal", "fast"}
ALLOWED_MNA = {"yes", "no"}
ALLOWED_BUSINESS_STAGE = {"owner", "want_to_open"}


async def get_connection():
    return await psycopg.AsyncConnection.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


async def init_db():
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            # Legacy tables are no longer used after schema simplification.
            for table_name in (
                "lead_contacts",
                "user_profiles",
                "warmup_delivery_logs",
                "warmup_messages",
                "user_questions",
                "user_scores",
            ):
                await cur.execute(f"DROP TABLE IF EXISTS {table_name};")

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    company TEXT,
                    contact_name TEXT,
                    contact_phone TEXT,
                    contact_email TEXT,
                    contact_position TEXT,
                    onboarding_consent TEXT,
                    contact_telegram TEXT,
                    company_website TEXT,
                    simulate_consent TEXT,
                    valuation_consent TEXT,
                    last_connection_at TIMESTAMP,
                    accountants_count INTEGER,
                    avg_salary INTEGER,
                    express_saving_6 BIGINT,
                    express_saving_12 BIGINT,
                    meeting_booked BOOLEAN DEFAULT FALSE,
                    advisory_band TEXT CHECK (advisory_band IN ('lt10', '10_20', 'gt20')),
                    active_clients_count INTEGER,
                    standardization_level TEXT CHECK (standardization_level IN ('high', 'medium', 'low')),
                    automation_level TEXT CHECK (automation_level IN ('none', 'partial', 'systems')),
                    precise_assessment TEXT,
                    margin_percent INTEGER,
                    growth_band TEXT CHECK (growth_band IN ('none', 'normal', 'fast')),
                    mna_interest TEXT CHECK (mna_interest IN ('yes', 'no')),
                    file_downloaded BOOLEAN DEFAULT FALSE,
                    uploaded_file_link TEXT,
                    valuation_revenue_mln DOUBLE PRECISION,
                    valuation_share_percent DOUBLE PRECISION,
                    valuation_profitability_percent DOUBLE PRECISION,
                    valuation_profit_mln DOUBLE PRECISION,
                    valuation_result_mln DOUBLE PRECISION,
                    valuation_c1 INTEGER,
                    valuation_c2 INTEGER,
                    valuation_c3 TEXT,
                    valuation_h INTEGER,
                    valuation_q8_level TEXT,
                    valuation_auto_tools TEXT,
                    valuation_auto_other TEXT,
                    valuation_rfcomp DOUBLE PRECISION,
                    valuation_new_result_mln DOUBLE PRECISION,
                    support_program_registered BOOLEAN DEFAULT FALSE,
                    business_stage TEXT CHECK (business_stage IN ('owner', 'want_to_open')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS company TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_name TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_phone TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_email TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_position TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_consent TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_telegram TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS company_website TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS simulate_consent TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_consent TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS last_connection_at TIMESTAMP;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS accountants_count INTEGER;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS avg_salary INTEGER;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS express_saving_6 BIGINT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS express_saving_12 BIGINT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS meeting_booked BOOLEAN DEFAULT FALSE;""")
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS advisory_band TEXT
                   CHECK (advisory_band IN ('lt10', '10_20', 'gt20'));"""
            )
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS active_clients_count INTEGER;""")
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS standardization_level TEXT
                   CHECK (standardization_level IN ('high', 'medium', 'low'));"""
            )
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS automation_level TEXT
                   CHECK (automation_level IN ('none', 'partial', 'systems'));"""
            )
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS precise_assessment TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS margin_percent INTEGER;""")
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS growth_band TEXT
                   CHECK (growth_band IN ('none', 'normal', 'fast'));"""
            )
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS mna_interest TEXT
                   CHECK (mna_interest IN ('yes', 'no'));"""
            )
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS file_downloaded BOOLEAN DEFAULT FALSE;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS uploaded_file_link TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_revenue_mln DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_share_percent DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_profitability_percent DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_profit_mln DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_result_mln DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_c1 INTEGER;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_c2 INTEGER;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_c3 TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_h INTEGER;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_q8_level TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_auto_tools TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_auto_other TEXT;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_rfcomp DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS valuation_new_result_mln DOUBLE PRECISION;""")
            await cur.execute("""ALTER TABLE users ADD COLUMN IF NOT EXISTS support_program_registered BOOLEAN DEFAULT FALSE;""")
            await cur.execute(
                """ALTER TABLE users ADD COLUMN IF NOT EXISTS business_stage TEXT
                   CHECK (business_stage IN ('owner', 'want_to_open'));"""
            )

            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS lead_email;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS lead_telegram;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS lead_phone;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS track;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS role;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS business_size;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS timeframe;""")
            await cur.execute("""ALTER TABLE users DROP COLUMN IF EXISTS motivation;""")

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS lead_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_name TEXT NOT NULL,
                    event_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_events_user_created
                ON lead_events (user_id, created_at DESC);
            """)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS push_delivery_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    post_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, post_id)
                );
            """)

            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_push_delivery_user_post
                ON push_delivery_logs (user_id, post_id);
            """)


        await conn.commit()
    finally:
        await conn.close()


async def upsert_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> int:
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, last_connection_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_connection_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, (telegram_id, username, first_name, last_name))

            row = await cur.fetchone()

        await conn.commit()
        return row["id"]
    finally:
        await conn.close()


async def add_event(user_id: int, event_name: str, event_value: str | None = None):
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO lead_events (user_id, event_name, event_value)
                VALUES (%s, %s, %s);
            """, (user_id, event_name, event_value))

        await conn.commit()
    finally:
        await conn.close()


async def save_profile_field(user_id: int, field_name: str, value: str):
    if field_name not in ALLOWED_PROFILE_FIELDS:
        raise ValueError(f"Недопустимое поле профиля: {field_name}")

    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE users
                SET {field_name} = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (value, user_id),
            )

        await conn.commit()
    finally:
        await conn.close()


async def save_funnel_fields(user_id: int, **fields):
    if not fields:
        return

    unknown = set(fields) - ALLOWED_FUNNEL_FIELDS
    if unknown:
        raise ValueError(f"Недопустимые funnel-поля: {', '.join(sorted(unknown))}")

    if "standardization_level" in fields and fields["standardization_level"] not in ALLOWED_STANDARDIZATION:
        raise ValueError(f"Недопустимая стандартизация: {fields['standardization_level']}")
    if "automation_level" in fields and fields["automation_level"] not in ALLOWED_AUTOMATION:
        raise ValueError(f"Недопустимая автоматизация: {fields['automation_level']}")
    if "advisory_band" in fields and fields["advisory_band"] not in ALLOWED_ADVISORY:
        raise ValueError(f"Недопустимый advisory: {fields['advisory_band']}")
    if "growth_band" in fields and fields["growth_band"] not in ALLOWED_GROWTH:
        raise ValueError(f"Недопустимый рост: {fields['growth_band']}")
    if "mna_interest" in fields and fields["mna_interest"] not in ALLOWED_MNA:
        raise ValueError(f"Недопустимый M&A: {fields['mna_interest']}")
    if "business_stage" in fields and fields["business_stage"] not in ALLOWED_BUSINESS_STAGE:
        raise ValueError(f"Недопустимый этап бизнеса: {fields['business_stage']}")

    set_parts = []
    values = []
    for field_name, value in fields.items():
        set_parts.append(f"{field_name} = %s")
        values.append(value)
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    values.append(user_id)

    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE users
                SET {", ".join(set_parts)}
                WHERE id = %s;
                """,
                values,
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_users_for_export():
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    id,
                    telegram_id,
                    username,
                    created_at,
                    updated_at,
                    company,
                    contact_name,
                    contact_phone,
                    contact_email,
                    company_website,
                    simulate_consent,
                    valuation_consent,
                    last_connection_at,
                    accountants_count,
                    avg_salary,
                    express_saving_6,
                    express_saving_12,
                    meeting_booked,
                    advisory_band,
                    active_clients_count,
                    standardization_level,
                    automation_level,
                    COALESCE(
                        precise_assessment,
                        CASE
                            WHEN express_saving_6 IS NOT NULL AND express_saving_12 IS NOT NULL THEN
                                LEAST(express_saving_6, express_saving_12)::text || ' – ' ||
                                GREATEST(express_saving_6, express_saving_12)::text || ' ₽/мес'
                            ELSE NULL
                        END
                    ) AS precise_assessment,
                    margin_percent,
                    growth_band,
                    mna_interest,
                    file_downloaded,
                    uploaded_file_link,
                    valuation_revenue_mln,
                    valuation_share_percent,
                    valuation_profitability_percent,
                    valuation_profit_mln,
                    valuation_result_mln,
                    valuation_c1,
                    valuation_c2,
                    valuation_c3,
                    valuation_h,
                    valuation_q8_level,
                    valuation_auto_tools,
                    valuation_auto_other,
                    valuation_rfcomp,
                    valuation_new_result_mln,
                    support_program_registered,
                    business_stage
                FROM users
                ORDER BY id ASC;
            """)
            rows = await cur.fetchall()
        return rows
    finally:
        await conn.close()


async def get_all_users_for_push():
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, telegram_id, created_at
                FROM users
                ORDER BY id ASC;
            """)
            rows = await cur.fetchall()
        return rows
    finally:
        await conn.close()


async def was_push_sent(user_id: int, post_id: str) -> bool:
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM push_delivery_logs
                WHERE user_id = %s AND post_id = %s
                LIMIT 1;
                """,
                (user_id, post_id),
            )
            row = await cur.fetchone()
        return row is not None
    finally:
        await conn.close()


async def log_push_delivery(user_id: int, post_id: str):
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO push_delivery_logs (user_id, post_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, post_id) DO NOTHING;
                """,
                (user_id, post_id),
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_tool_consent(user_id: int, tool_name: str) -> bool:
    if tool_name not in {"simulate", "valuation"}:
        raise ValueError(f"Unsupported tool for consent lookup: {tool_name}")

    column_name = f"{tool_name}_consent"

    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT {column_name}
                FROM users
                WHERE id = %s;
                """,
                (user_id,),
            )
            row = await cur.fetchone()

        if not row:
            return False

        return row[column_name] == "accepted"
    finally:
        await conn.close()


async def get_user_personal_data(user_id: int) -> dict[str, str]:
    conn = await get_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT contact_name, contact_email, contact_phone, company, company_website
                FROM users
                WHERE id = %s;
                """,
                (user_id,),
            )
            row = await cur.fetchone()

        if not row:
            return {
                "contact_name": "",
                "contact_email": "",
                "contact_phone": "",
                "company": "",
                "company_website": "",
            }

        return {
            "contact_name": (row.get("contact_name") or "").strip(),
            "contact_email": (row.get("contact_email") or "").strip(),
            "contact_phone": (row.get("contact_phone") or "").strip(),
            "company": (row.get("company") or "").strip(),
            "company_website": (row.get("company_website") or "").strip(),
        }
    finally:
        await conn.close()
