import calendar
from datetime import date, datetime

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from app.config import CALENDLY_PUBLIC_LINK


def _safe_calendly_link() -> str:
    raw = (CALENDLY_PUBLIC_LINK or "").strip()
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")) and len(raw) > 1:
        raw = raw[1:-1].strip()
    if not raw:
        return "https://calendly.com/4davyd0vcreate/30min"
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw


def persistent_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню бота")],
            [KeyboardButton(text="Калькулятор экономии")],
            [KeyboardButton(text="Сделка и рост")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите раздел",
    )


def tool_navigation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 В меню"), KeyboardButton(text="⬅️ Назад")],
            [KeyboardButton(text="⏭ Пропустить"), KeyboardButton(text="❌ Отменить")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Управление инструментом",
    )


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на встречу", callback_data="stub:book_meeting")],
            [InlineKeyboardButton(text="🎤 Встретиться на мероприятиях", callback_data="stub:events")],
            [InlineKeyboardButton(text="❓ Часто задаваемые вопросы о сделке", callback_data="valuation:menu:faq")],
            [InlineKeyboardButton(text="🧩 Продукты и услуги (скоро)", callback_data="stub:products")],
            [InlineKeyboardButton(text="🎬 Видео и кейсы (скоро)", callback_data="stub:videos")],
        ]
    )


def website_optional_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Нету сайта", callback_data="onboarding:no_site")],
        ]
    )


def tool_consent_keyboard(nda_checked: bool, terms_checked: bool, tool_name: str) -> InlineKeyboardMarkup:
    nda_icon = "✅" if nda_checked else "⬜"
    terms_icon = "✅" if terms_checked else "⬜"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{nda_icon} NDA from AIVEL side", callback_data="consent:toggle:nda")],
            [InlineKeyboardButton(text=f"{terms_icon} Terms + Privacy + Marketing", callback_data="consent:toggle:terms")],
            [InlineKeyboardButton(text="Соглашаюсь", callback_data=f"consent:submit:{tool_name}")],
            [InlineKeyboardButton(text="Назад", callback_data="consent:back")],
        ]
    )


def simulate_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Начать экспресс-оценку", callback_data="simulate:mode:express")],
            [InlineKeyboardButton(text="📊 Скачать Excel-файл", callback_data="simulate:mode:pro")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="simulate:back")],
        ]
    )


def simulate_results_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на встречу", callback_data="stub:book_meeting")],
            [InlineKeyboardButton(text="📈 Хотите точнее? +5 вопросов", callback_data="simulate:precise:more5")],
            [InlineKeyboardButton(text="📊 Скачать Excel-файл", callback_data="simulate:mode:pro")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="simulate:back")],
        ]
    )


def simulate_skip_question_keyboard(question_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data=f"simulate:express:skip:{question_key}")],
            [InlineKeyboardButton(text="Назад", callback_data="simulate:back")],
        ]
    )


def simulate_precise_skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data=callback_data)],
        ]
    )


def simulate_contacts_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поделиться", callback_data="simulate:contacts:share")],
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data="simulate:contacts:skip")],
        ]
    )


def simulate_contact_field_keyboard(skip_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить поле", callback_data=skip_callback)],
        ]
    )


def simulate_precise_ops_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="40-50%", callback_data="simulate:precise:ops:40_50")],
            [InlineKeyboardButton(text="50-70%", callback_data="simulate:precise:ops:50_70")],
            [InlineKeyboardButton(text="70%+", callback_data="simulate:precise:ops:70_plus")],
        ]
    )


def simulate_precise_complex_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, много (>30%)", callback_data="simulate:precise:complex:many")],
            [InlineKeyboardButton(text="Некоторые (10–30%)", callback_data="simulate:precise:complex:some")],
            [InlineKeyboardButton(text="Мало (<10%)", callback_data="simulate:precise:complex:few")],
        ]
    )


def simulate_precise_results_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на встречу", callback_data="stub:book_meeting")],
            [InlineKeyboardButton(text="📈 Хотите точнее? +5 вопросов", callback_data="simulate:precise:more5")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="simulate:back")],
        ]
    )


def simulate_plus3_standardization_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Высокая стандартизация",
                    callback_data="simulate:plus3:std:high",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Средняя стандартизация",
                    callback_data="simulate:plus3:std:medium",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Низкая стандартизация",
                    callback_data="simulate:plus3:std:low",
                )
            ],
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data="simulate:plus3:std:skip")],
        ]
    )


def simulate_plus3_automation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Нет, всё вручную — только 1С и Excel", callback_data="simulate:plus3:auto:none")],
            [
                InlineKeyboardButton(
                    text="Частично — макросы, автовыгрузки, шаблоны, таск-менеджер",
                    callback_data="simulate:plus3:auto:partial",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Да, есть системы — используем RPA/ботов/AI",
                    callback_data="simulate:plus3:auto:systems",
                )
            ],
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data="simulate:plus3:auto:skip")],
        ]
    )


def simulate_plus3_advisory_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Менее 10%", callback_data="simulate:plus3:advisory:lt10")],
            [InlineKeyboardButton(text="10-20%", callback_data="simulate:plus3:advisory:10_20")],
            [InlineKeyboardButton(text="Более 20%", callback_data="simulate:plus3:advisory:gt20")],
            [InlineKeyboardButton(text="Пропустить вопрос", callback_data="simulate:plus3:advisory:skip")],
        ]
    )


def simulate_growth_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Нет", callback_data="simulate:post:growth:none")],
            [InlineKeyboardButton(text="Да, обычный рост +5–20%", callback_data="simulate:post:growth:normal")],
            [InlineKeyboardButton(text="Да, быстрый рост >20%", callback_data="simulate:post:growth:fast")],
        ]
    )


def simulate_mna_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="simulate:post:mna:yes")],
            [InlineKeyboardButton(text="Нет", callback_data="simulate:post:mna:no")],
        ]
    )


def simulate_deep_assessment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Скачать Excel-файл", callback_data="simulate:deep:download")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="simulate:deep:back")],
        ]
    )


def simulate_deep_wait_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправил по почте", callback_data="simulate:deep:sent_email")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="simulate:deep:back_wait")],
        ]
    )


def meeting_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    month_name = datetime(year, month, 1).strftime("%B %Y")

    inline_keyboard = [[InlineKeyboardButton(text=month_name, callback_data="meeting:noop")]]
    inline_keyboard.append(
        [InlineKeyboardButton(text=day, callback_data="meeting:noop") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]
    )

    today = date.today()
    for week in month_days:
        row = []
        for d in week:
            if d == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="meeting:noop"))
                continue
            selected = date(year, month, d)
            if selected < today:
                row.append(InlineKeyboardButton(text="·", callback_data="meeting:noop"))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(d),
                        callback_data=f"meeting:date:pick:{selected.isoformat()}",
                    )
                )
        inline_keyboard.append(row)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    inline_keyboard.append(
        [
            InlineKeyboardButton(text="◀️", callback_data=f"meeting:date:nav:{prev_year}-{prev_month:02d}"),
            InlineKeyboardButton(text="Назад", callback_data="meeting:back"),
            InlineKeyboardButton(text="▶️", callback_data=f"meeting:date:nav:{next_year}-{next_month:02d}"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def meeting_slots_keyboard(slot_values: list[str]) -> InlineKeyboardMarkup:
    inline_keyboard = [[InlineKeyboardButton(text=slot, callback_data=f"meeting:slot:{slot}")] for slot in slot_values]
    inline_keyboard.append([InlineKeyboardButton(text="Другое время", callback_data="meeting:slot:other")])
    inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="meeting:back")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def meeting_custom_time_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for hour in range(9, 22):
        rows.append([InlineKeyboardButton(text=f"{hour:02d}:00", callback_data=f"meeting:time:{hour:02d}:00")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="meeting:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def meeting_waiting_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="meeting:back")],
        ]
    )


def valuation_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Быстрая оценка за 2 минуты", callback_data="valuation:mode:express")],
            [InlineKeyboardButton(text="⬇️ Заполнить в Excel для менеджера", callback_data="valuation:mode:excel")],
            [InlineKeyboardButton(text="❓ Часто задаваемые вопросы о сделке", callback_data="valuation:mode:faq")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="valuation:back")],
        ]
    )


def valuation_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали⚡", callback_data="valuation:express:start")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="valuation:back")],
        ]
    )


def valuation_share_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="<40%", callback_data="valuation:share:lt40")],
            [InlineKeyboardButton(text="40-60%", callback_data="valuation:share:40_60")],
            [InlineKeyboardButton(text="60-80%", callback_data="valuation:share:60_80")],
            [InlineKeyboardButton(text=">80%", callback_data="valuation:share:gt80")],
            [
                InlineKeyboardButton(
                    text="Я не знаю, но это основная часть нашего бизнеса",
                    callback_data="valuation:share:unknown_main",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Я не знаю, но это незначительная часть нашего бизнеса",
                    callback_data="valuation:share:unknown_small",
                )
            ],
        ]
    )


def valuation_low_share_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Обсудить выделение на звонке", url=_safe_calendly_link())],
            [InlineKeyboardButton(text="👋 Спасибо, не сейчас", callback_data="valuation:low_share:not_now")],
        ]
    )


def valuation_profitability_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="15–20%", callback_data="valuation:profit:15_20")],
            [InlineKeyboardButton(text="20–25%", callback_data="valuation:profit:20_25")],
            [InlineKeyboardButton(text="25–30%", callback_data="valuation:profit:25_30")],
            [InlineKeyboardButton(text="30–35%", callback_data="valuation:profit:30_35")],
            [InlineKeyboardButton(text="Больше 35%", callback_data="valuation:profit:gt35")],
            [InlineKeyboardButton(text="Я не знаю", callback_data="valuation:profit:unknown")],
        ]
    )


def valuation_continue_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="valuation:continue:yes")],
            [InlineKeyboardButton(text="Нет", callback_data="valuation:continue:no")],
        ]
    )


def valuation_q6_share_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Менее 20%", callback_data="valuation:q6:lt20")],
            [InlineKeyboardButton(text="20–40%", callback_data="valuation:q6:20_40")],
            [InlineKeyboardButton(text="40–60%", callback_data="valuation:q6:40_60")],
            [InlineKeyboardButton(text="60–80%", callback_data="valuation:q6:60_80")],
            [InlineKeyboardButton(text="Более 80%", callback_data="valuation:q6:gt80")],
        ]
    )


def valuation_q8_automation_level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Нет — работаем в 1С и Excel", callback_data="valuation:q8:none")],
            [InlineKeyboardButton(text="Частично — макросы, автовыгрузки, таск-менеджер", callback_data="valuation:q8:partial")],
            [InlineKeyboardButton(text="Да — RPA, боты или AI-решения", callback_data="valuation:q8:advanced")],
        ]
    )


def valuation_automation_tools_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    options = [
        ("rpa", "RPA (UiPath, PIX, Robin и т.д.)"),
        ("bots", "Боты для 1С / Telegram"),
        ("ocr", "OCR / распознавание документов"),
        ("ai", "AI-решения (GPT, Copilot и др.)"),
        ("bi", "BI-система (Power BI, Metabase и др.)"),
    ]

    rows = []
    for key, label in options:
        icon = "✅" if key in selected else "⬜"
        rows.append([InlineKeyboardButton(text=f"{icon} {label}", callback_data=f"valuation:auto:toggle:{key}")])

    rows.append([InlineKeyboardButton(text="✍️ Другое (напишите в чат)", callback_data="valuation:auto:other:hint")])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="valuation:auto:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def valuation_excel_offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать Excel-файл", callback_data="valuation:excel:download")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="valuation:excel:menu")],
        ]
    )


def valuation_idle_followup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Модели", callback_data="valuation:idle:models")],
            [InlineKeyboardButton(text="❓ Вопросы", callback_data="valuation:idle:faq")],
        ]
    )


def valuation_faq_topics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оценка и цена", callback_data="valuation:faq:topic:price")],
            [InlineKeyboardButton(text="Кто за что отвечает", callback_data="valuation:faq:topic:roles")],
            [InlineKeyboardButton(text="Как проходит сделка", callback_data="valuation:faq:topic:process")],
            [InlineKeyboardButton(text="Внедрение ИИ", callback_data="valuation:faq:topic:ai")],
            [InlineKeyboardButton(text="Что меняется в фирме", callback_data="valuation:faq:topic:changes")],
            [InlineKeyboardButton(text="Юридические вопросы", callback_data="valuation:faq:topic:legal")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="valuation:excel:menu")],
        ]
    )


def valuation_faq_price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Как оценивается моя фирма?", callback_data="valuation:faq:q:price_calc")],
            [InlineKeyboardButton(text="А если у меня долги?", callback_data="valuation:faq:q:price_debt")],
            [InlineKeyboardButton(text="Сколько я получу за 25%?", callback_data="valuation:faq:q:price_25")],
            [InlineKeyboardButton(text="Cash-In vs Cash-Out — что выгоднее?", callback_data="valuation:faq:q:price_cash")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_roles_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Что изменится в управлении?", callback_data="valuation:faq:q:roles_mgmt")],
            [InlineKeyboardButton(text="Могут ли меня уволить?", callback_data="valuation:faq:q:roles_fire")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_process_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Шаги от знакомства до сделки", callback_data="valuation:faq:q:process_steps")],
            [InlineKeyboardButton(text="А можно быстрее?", callback_data="valuation:faq:q:process_fast")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Как быстро заработает ИИ?", callback_data="valuation:faq:q:ai_speed")],
            [InlineKeyboardButton(text="Сколько стоит внедрение?", callback_data="valuation:faq:q:ai_cost")],
            [InlineKeyboardButton(text="Что автоматизируется?", callback_data="valuation:faq:q:ai_scope")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_changes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Что изменится для моих клиентов?", callback_data="valuation:faq:q:changes_clients")],
            [InlineKeyboardButton(text="А что с моей командой?", callback_data="valuation:faq:q:changes_team")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_legal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Как юридически оформлена сделка: документы, права и защита?", callback_data="valuation:faq:q:legal_structure")],
            [InlineKeyboardButton(text="А если я захочу выйти?", callback_data="valuation:faq:q:legal_exit")],
            [InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")],
        ]
    )


def valuation_faq_question_numbers_keyboard(topic: str, total: int) -> InlineKeyboardMarkup:
    rows = []
    for idx in range(1, total + 1):
        rows.append(
            [InlineKeyboardButton(text=f"Вопрос {idx}", callback_data=f"valuation:faq:{topic}:q{idx}")]
        )
    rows.append([InlineKeyboardButton(text="↩️ К темам", callback_data="valuation:faq:topics")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendly_meeting_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Открыть Calendly", url=_safe_calendly_link())],
        ]
    )


def meeting_registration_check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, зарегистрировался", callback_data="meeting:external:yes")],
            [InlineKeyboardButton(text="Нет, передумал", callback_data="meeting:external:no")],
        ]
    )
