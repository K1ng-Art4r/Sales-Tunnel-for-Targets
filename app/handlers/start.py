import logging
import re
import asyncio
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.calendly import (
    CalendlyNotConfiguredError,
    CalendlyRequestError,
    book_slot,
    get_available_hour_slots,
    is_configured as calendly_is_configured,
    is_slot_available,
)
from app.config import BOT_TOKEN, MEETING_TIMEZONE
from app.config import GOOGLE_SHEETS_API_KEY, GOOGLE_SHEETS_RANGE, GOOGLE_SHEETS_SPREADSHEET_ID
from app.db import add_event, get_user_personal_data, save_funnel_fields, save_profile_field, upsert_user
from app.events import EventsConfigError, EventsRequestError, fetch_events, format_events_message
from app.keyboards import (
    meeting_calendar_keyboard,
    calendly_meeting_keyboard,
    meeting_registration_check_keyboard,
    meeting_custom_time_keyboard,
    meeting_slots_keyboard,
    meeting_waiting_keyboard,
    menu_keyboard,
    gift_keyboard,
    support_program_business_stage_keyboard,
    support_program_navigation_keyboard,
    persistent_main_keyboard,
    tool_navigation_keyboard,
    website_optional_keyboard,
    simulate_deep_assessment_keyboard,
    simulate_deep_wait_keyboard,
    simulate_mode_keyboard,
    simulate_plus3_advisory_keyboard,
    simulate_plus3_automation_keyboard,
    simulate_plus3_standardization_keyboard,
    simulate_growth_keyboard,
    simulate_mna_keyboard,
    simulate_contacts_choice_keyboard,
    simulate_results_keyboard,
    valuation_continue_keyboard,
    valuation_intro_keyboard,
    valuation_low_share_keyboard,
    valuation_mode_keyboard,
    valuation_profitability_keyboard,
    valuation_share_keyboard,
    valuation_q6_share_keyboard,
    valuation_q8_automation_level_keyboard,
    valuation_automation_tools_keyboard,
    valuation_excel_offer_keyboard,
    valuation_idle_followup_keyboard,
    valuation_faq_topics_keyboard,
    valuation_faq_question_numbers_keyboard,
)
from app.scoring import (
    calculate_express_operation_savings,
    calculate_precise_savings_from_express,
)
from app.states import MeetingBookingFlow, SimulateFlow, SupportProgramFlow, ValuationFlow

router = Router()
router.message.filter(F.from_user.is_bot == False)
router.callback_query.filter(F.from_user.is_bot == False)
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

URL_RE = re.compile(r"^(https?://)?(www\.)?[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+(/.*)?$", re.IGNORECASE)
SUPPORT_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s'-]*$")
SUPPORT_PHONE_RE = re.compile(r"^\+?[0-9()\s.-]{10,20}$")

ONBOARDING_PROMO_TEXT = (
    "Добро пожаловать в Aivel!\n"
    "Мы автоматизируем до 95% бухгалтерских операций с помощью AI. "
    "Забудьте о проблемах с наймом — фокусируйтесь на продажах и клиентах.\n\n"
    "Что здесь:\n"
    "📊 Новости, события, новые партнёры\n"
    "💰 Калькулятор вашей экономии\n"
    "📈 Сделка и рост\n"
    "📅 Запись на встречу со специалистом\n\n"
    "🎁 У нас для вас приветственный подарок: "
    "Анализатор клиентских чатов в Битрикс24 и Telegram (нажмите здесь)\n\n"
    "👨‍🏫⭐️ Мы предлагаем программу поддержки вашего бизнеса — независимо от того, "
    "начинаете ли вы с нуля или уже имеете опыт. Наше наставничество поможет вам "
    "уверенно действовать с фокусом на рост. Присоединяйтесь прямо сейчас."
)


SUPPORT_PROGRAM_INTRO_TEXT = (
    "👨‍🏫 <b>Программа поддержки бизнеса</b>\n\n"
    "У вас уже есть своя фирма или вы только планируете её открыть?\n\n"
    "🤝 Получите поддержку от владельца бизнеса из нашей сети. В рамках программы "
    "поддержки будут доступны эфиры и материалы от экспертов и партнеров.\n\n"
    "⭐️ <b>Ближайшая сессия</b> запланирована с Натальей Бланкет — учредителем "
    "и генеральным директором компании, обслуживающей 400+ клиентов, опытным наставником.\n\n"
    "📝 Чтобы зарегистрироваться, укажите свое имя, номер телефона и адрес электронной почты."
)
SUPPORT_PROGRAM_FINAL_TEXT = (
    "✅ <b>Спасибо за регистрацию!</b>\n\n"
    "Мы скоро пришлем вам информацию.\n\n"
    "А пока узнайте больше о компании AIVEL и о нашем предложении по сотрудничеству "
    "прямо в этом боте — воспользуйтесь меню.\n\n"
    "Здесь мы также регулярно делимся новостями, полезными советами и примерами из практики."
)

CHAT_ANALYZER_GIFT_TEXT = (
    "Как за 15 минут увидеть, что происходит в переписке вашего сотрудника с клиентом — "
    "не читая весь чат\n"
    "Мы подготовили промпт для ChatGPT, который анализирует переписку и выдаёт "
    "структурированный отчёт.\n\n"
    "Вы получаете:\n"
    "— 🔴 Уровень риска — где ситуация близка к конфликту\n"
    "— ⚠️ Претензию — явное и скрытое недовольство клиента\n"
    "— 💬 Оценку формата общения — насколько профессионально отвечает сотрудник\n"
    "— 🎯 Готовую рекомендацию — что именно проверить и кому позвонить\n"
    "— ✉️ Готовый ответ клиенту — можно сразу передать сотруднику\n\n"
    "Работает с Telegram и Битрикс24. Несколько клиентов — одним запросом, "
    "получите сводку по всем.\n"
    "Никаких новых сервисов — только ChatGPT (бесплатно) и 15 минут времени."
)
CHAT_ANALYZER_PDF_PATH = PROJECT_ROOT / "Анализ_качества_переписки_с_клиентом.pdf"

TOOL_PLACEHOLDER_TEXT = (
    "Инструмент пока в режиме заглушки."
    " На следующем шаге здесь будет полноценная интерактивная симуляция."
)
MENU_TEXT = "Меню бота:"
BOOK_MEETING_TEXT = "Давайте запишем вас на встречу в Calendly."
SIMULATE_MODE_TEXT = (
    "💰 <b>Калькулятор экономии с Aivel</b>\n\n"
    "Выберите уровень детализации расчёта:\n\n"
    "⚡ <b>Экспресс-оценка (1 минута)</b>\n"
    "2 вопроса → мгновенный результат\n"
    "Для первого знакомства и быстрой оценки порядка цифр\n\n"
    "📊 <b>Профессиональная оценка (60–90 минут)</b>\n"
    "Excel-опросник: ~45 полей данных → максимальная точность\n"
    "Полный финансовый анализ с моделированием ROI, NPV, и планом внедрения"
)
SIMULATE_PRO_TEXT = (
    "🎯 Серьёзно рассматриваете внедрение? Загрузите Excel — получите полный бизнес-кейс от нашей команды.\n"
    "📥 Скачать Excel-файл\n"
    "📤 Заполнили? Загрузить обратно или отправьте это на: success@aivel.ai\n"
    "После загрузки мы подготовим детальный бизнес-кейс и свяжемся с вами в течение 2 рабочих дней.\n\n"
    "📊 Что внутри Excel-опросника?\n\n"
    "1️⃣ Цифры (Лист 1) — 20 полей, 25-30 минут\n"
    "• Выручка и прибыль за 3 года\n"
    "• Структура клиентов и средний чек\n"
    "• Отток и концентрация выручки\n"
    "• Маржинальность и повторяемость\n\n"
    "2️⃣ Компания и рынок (Лист 2) — 15 полей, 10-15 минут\n"
    "• Профиль компании и юрструктура\n"
    "• Рыночная позиция и конкуренты\n"
    "• Структура услуг и допродажи\n"
    "• Технологии и автоматизация\n\n"
    "3️⃣ Основатели (Лист 3) — 10 полей, 5-10 минут\n"
    "• Состав собственников\n"
    "• Роль в операционке\n"
    "• Предпочтения по сделке\n"
    "• Интерес к M&A\n\n"
    "Итого: 45 полей, 30-40 минут\n"
    "Можно заполнять частями, сохранять, возвращаться. Все поля с подсказками и примерами."
)
SIMULATE_PRO_MISSING_TEXT = (
    "Не удалось найти Excel-файл в проекте.\n"
    "Пожалуйста, добавьте .xlsx в репозиторий (например, в app/assets/) и попробуйте снова."
)
STANDARDIZATION_LABELS = {
    "high": "Высокая",
    "medium": "Средняя",
    "low": "Низкая",
}
AUTOMATION_LABELS = {
    "none": "Нет, всё вручную",
    "partial": "Частично",
    "systems": "Да, есть системы",
}
ADVISORY_LABELS = {
    "lt10": "Менее 10%",
    "10_20": "10-20%",
    "gt20": "Более 20%",
}
VALUATION_SHARE_MAP = {
    "40_60": 55.0,
    "60_80": 70.0,
    "gt80": 85.0,
    "unknown_main": 60.0,
}
VALUATION_LOW_SHARE_OPTIONS = {"lt40", "unknown_small"}
VALUATION_PROFITABILITY_MAP = {
    "15_20": 17.5,
    "20_25": 22.5,
    "25_30": 27.5,
    "30_35": 30.0,
    "gt35": 35.0,
    "unknown": 25.0,
}
WAIT_FILE_TEXT = (
    "Ожидаем ваш файл.\n\n"
    "Вы можете загрузить Excel сюда или нажать «Отправил по почте», если уже отправили на success@aivel.ai."
)
THANKS_DEEP_TEXT = "Спасибо! С вами свяжутся в течение 2 рабочих дней."
THANKS_TOOL_TEXT = "Спасибо, что воспользовались нашим инструментом, надеемся он оказался полезным."
NO_SITE_MARKER = "нет сайта"
MISSING_PERSONAL_DATA_TEXT = (
    "Чтобы мы могли дать качественную обратную связь по вашему Excel,\n"
    "пожалуйста, заполните все персональные данные.\n"
    "После этого мы свяжемся с вами в течение 2 рабочих дней."
)
INACTIVE_TOOL_BUTTON_TEXT = (
    "Эта кнопка больше не активна, для использования необходимо ещё раз воспользоваться инструментом."
)
MEETING_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_EXPRESS_ACCOUNTANTS = 15
DEFAULT_EXPRESS_SALARY = 120000
DEFAULT_VALUATION_REVENUE_MLN = 30.0
DEFAULT_VALUATION_SHARE_OPTION = "60_80"
DEFAULT_VALUATION_PROFITABILITY_OPTION = "unknown"
VALUATION_RUB_INPUT_THRESHOLD = 1000
VALUATION_MULTIPLE = 2.5
VALUATION_IDLE_TIMEOUT_SECONDS = 60
VALUATION_Q6_RF2_MAP = {
    "lt20": 1.1,
    "20_40": 1.0,
    "40_60": 0.9,
    "60_80": 0.8,
    "gt80": 0.7,
}
VALUATION_POST_RESULT_STATE = {
    ValuationFlow.precise_post_result.state,
}
VALUATION_IDLE_TASKS: dict[int, asyncio.Task] = {}
SIMULATE_START_LOCKS: dict[int, datetime] = {}
SIMULATE_START_LOCK_SECONDS = 5
VALUATION_EXCEL_TEXT = (
    "🎯 Если вы серьёзно рассматриваете партнёрство с нашим участием в технологиях и финансировании, "
    "давайте заполним наш подробный Excel-инструмент для оценки сделки.\n"
    "Загрузите Excel — получите полный бизнес-кейс от нашей команды."
)
VALUATION_MODELS_IMAGE_URL = "https://disk.yandex.com/i/SXmB484oG0gfzg"
VALUATION_ROLES_IMAGE_URL = "https://disk.yandex.com/i/bxE4nm-98rX3aA"



async def get_db_user_id(message_or_callback: Message | CallbackQuery) -> int:
    tg_user = message_or_callback.from_user
    if tg_user is None or tg_user.is_bot:
        raise ValueError("Bot-originated update cannot be mapped to app user")
    return await upsert_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )


async def send_onboarding_complete(message: Message):
    await message.answer(
        ONBOARDING_PROMO_TEXT,
        parse_mode="HTML",
        reply_markup=gift_keyboard(),
    )
    await message.answer("Выберите раздел в меню ниже 👇", reply_markup=persistent_main_keyboard())



def is_valid_support_name(value: str) -> bool:
    normalized = " ".join(value.strip().split())
    return bool(SUPPORT_NAME_RE.match(normalized))


def is_valid_support_phone(value: str) -> bool:
    normalized = value.strip()
    digits = re.sub(r"\D", "", normalized)
    return bool(SUPPORT_PHONE_RE.match(normalized)) and 10 <= len(digits) <= 15


def is_valid_support_email(value: str) -> bool:
    return bool(MEETING_EMAIL_RE.match(value.strip().lower()))


def parse_positive_int(raw_value: str) -> int | None:
    normalized = raw_value.replace(" ", "").replace(",", "").replace("_", "")
    if not normalized.isdigit():
        return None
    value = int(normalized)
    return value if value > 0 else None


def parse_float(raw_value: str) -> float | None:
    normalized = raw_value.strip().replace(" ", "").replace(",", ".").replace("_", "")
    if normalized.count(".") > 1:
        return None
    try:
        value = float(normalized)
    except ValueError:
        return None
    return value


def valuation_rf1_score(total_clients: int, key_clients: int) -> float:
    ratio = (key_clients / total_clients) * 100
    if ratio <= 10:
        return 1.1
    if ratio <= 20:
        return 1.0
    if ratio <= 35:
        return 0.9
    if ratio <= 50:
        return 0.8
    return 0.7


def valuation_rf3_score(total_clients: int) -> float:
    if total_clients >= 200:
        return 1.1
    if 150 <= total_clients <= 200:
        return 1.0
    if 100 <= total_clients <= 149:
        return 0.9
    if 50 <= total_clients <= 99:
        return 0.8
    return 0.7


def format_mln(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def cancel_valuation_idle_task(user_id: int) -> None:
    task = VALUATION_IDLE_TASKS.pop(user_id, None)
    if task and not task.done():
        task.cancel()


async def schedule_valuation_idle_followup(message: Message, state: FSMContext, user_id: int):
    cancel_valuation_idle_task(user_id)
    marker = datetime.utcnow().isoformat()
    await state.update_data(valuation_idle_marker=marker)

    async def _idle_ping():
        try:
            await asyncio.sleep(VALUATION_IDLE_TIMEOUT_SECONDS)
            current_state = await state.get_state()
            data = await state.get_data()
            if current_state not in VALUATION_POST_RESULT_STATE:
                return
            if data.get("valuation_idle_marker") != marker:
                return
            await message.answer(
                "Хотели бы вы узнать о наших моделях сотрудничества или предпочли бы ознакомиться с разделом «Вопросы»?",
                reply_markup=valuation_idle_followup_keyboard(),
            )
        except asyncio.CancelledError:
            return

    VALUATION_IDLE_TASKS[user_id] = asyncio.create_task(_idle_ping())


async def send_valuation_faq_topics(message: Message):
    await message.answer(
        "Всё о сделке — частые вопросы ❓\n\n"
        "Выберите тему:",
        reply_markup=valuation_faq_topics_keyboard(),
    )


async def reset_support_program_if_active(state: FSMContext, user_id: int):
    current_state = await state.get_state()
    support_states = {flow_state.state for flow_state in SupportProgramFlow.__all_states__}
    if current_state in support_states:
        await save_funnel_fields(user_id, support_program_registered=False)


async def show_main_menu(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    await reset_support_program_if_active(state, user_id)
    await state.clear()
    await add_event(user_id, "menu_opened")
    await message.answer(
        "Главное меню. Нижняя клавиатура обновлена 👇",
        reply_markup=persistent_main_keyboard(),
    )
    await message.answer(MENU_TEXT, reply_markup=menu_keyboard())


def is_tool_callback(callback_data: str) -> bool:
    if callback_data.startswith("simulate:"):
        return True
    if callback_data == "valuation:menu:faq" or callback_data.startswith("valuation:faq:"):
        return False
    return callback_data.startswith("valuation:")


async def reject_inactive_tool_callback(callback: CallbackQuery, state: FSMContext) -> bool:
    callback_data = callback.data or ""
    if await state.get_state() is not None or not is_tool_callback(callback_data):
        return False

    user_id = await get_db_user_id(callback)
    await add_event(user_id, "inactive_tool_callback", callback_data)
    await callback.answer()
    await callback.message.answer(INACTIVE_TOOL_BUTTON_TEXT, reply_markup=persistent_main_keyboard())
    return True


async def restart_simulate_flow(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(SimulateFlow.mode_select)
    await message.answer(SIMULATE_MODE_TEXT, parse_mode="HTML", reply_markup=simulate_mode_keyboard())


async def restart_valuation_flow(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ValuationFlow.mode_select)
    await message.answer(
        "Ваша фирма 2.0 — это не продажа бизнеса. Это апгрейд.\n"
        "Мы покажем, как партнёрство с AIVEL может изменить экономику вашей фирмы: "
        "больше прибыли, автоматизация рутины и капитал для роста.\n"
        "Выберите, с чего начать:",
        reply_markup=valuation_mode_keyboard(),
    )


async def answer_stale_callback(callback: CallbackQuery, state: FSMContext, section: str | None = None):
    data = callback.data or ""
    current_state = await state.get_state()
    user_id = await get_db_user_id(callback)
    await add_event(user_id, "stale_or_unknown_callback", f"state={current_state};data={data}")

    if is_tool_callback(data):
        await callback.answer()
        await callback.message.answer(INACTIVE_TOOL_BUTTON_TEXT, reply_markup=persistent_main_keyboard())
        return

    if section is None:
        if data.startswith("simulate:"):
            section = "simulate"
        elif data.startswith("valuation:"):
            section = "valuation"
        elif data.startswith("meeting:") or data.startswith("stub:book_meeting"):
            section = "meeting"

    await callback.answer("Эта кнопка уже неактуальна, показываю актуальный раздел 👇", show_alert=False)

    if section == "simulate":
        await restart_simulate_flow(callback.message, state)
        return
    if section == "valuation":
        await restart_valuation_flow(callback.message, state)
        return
    if section == "meeting":
        await callback.message.answer(
            "Откройте Calendly по кнопке ниже 👇",
            reply_markup=calendly_meeting_keyboard(),
            disable_web_page_preview=True,
        )
        await callback.message.answer(
            "Вам удалось записаться на встречу?",
            reply_markup=meeting_registration_check_keyboard(),
        )
        return

    await show_main_menu(callback.message, state)


def valuation_faq_answers() -> dict[str, str]:
    return {
        "price_calc": (
            "Формула простая:\n"
            "<b>Чистая прибыль × 2.5 = стоимость фирмы</b>\n"
            "Например: прибыль 5.3 млн ₽ → оценка 13.3 млн ₽.\n\n"
            "Мультипликатор 2.5× — это стандарт для бухгалтерских фирм с устойчивой клиентской базой.\n"
            "Он может корректироваться в зависимости от клиентов, доли постоянных договоров и долговой нагрузки."
        ),
        "price_debt": (
            "Долги вычитаются из оценки.\n"
            "Пример: прибыль 8 млн × 2.5 = 20 млн ₽, долг 2 млн ₽.\n"
            "<b>Чистая стоимость: 18 млн ₽.</b>"
        ),
        "price_25": (
            "Зависит от формата сделки:\n\n"
            "💵 <b>Cash-Out</b> — деньги вам на руки: 25% от оценки.\n"
            "🏗️ <b>Cash-In</b> — деньги идут в компанию на рост.\n"
            "🔄 <b>Микс</b> — часть вам, часть в компанию."
        ),
        "price_cash": (
            "<b>Cash-In</b> обычно выгоднее через 2–3 года, если цель — рост.\n"
            "<b>Cash-Out</b> — для тех, кому важна ликвидность сейчас."
        ),
        "roles_mgmt": (
            "Что изменится в управлении:\n"
            "• Операционка и клиенты остаются за управляющим партнёром.\n"
            "• AIVEL берёт на себя ИИ/IT-платформу и со-лидит M&A и маркетинг.\n"
            "• Ключевые решения фиксируются в соглашении."
        ),
        "roles_fire": (
            "Нет. Вы — совладелец и управляющий партнёр.\n"
            "Ваш статус закреплён в акционерном соглашении, изменения возможны только по процедуре, "
            "согласованной обеими сторонами."
        ),
        "process_steps": (
            "Процесс обычно занимает 4–8 недель:\n"
            "1️⃣ Знакомство\n2️⃣ Анкета и оценка\n3️⃣ Персональная модель\n"
            "4️⃣ Переговоры по структуре\n5️⃣ Due diligence\n6️⃣ Подписание и запуск внедрения."
        ),
        "process_fast": (
            "Да, можно быстрее — до 3–4 недель, если документы готовы и формат сделки определён заранее."
        ),
        "ai_speed": (
            "Внедрение идёт в 3 этапа:\n"
            "⚙️ Месяцы 1–3: подключение и настройка\n"
            "🚀 Месяцы 4–6: первые результаты\n"
            "🏆 Месяцы 7–18: максимальная автоматизация."
        ),
        "ai_cost": (
            "Зависит от формата:\n"
            "• Без сделки (только ИИ): 2–3 млн ₽ за внедрение.\n"
            "• В партнёрстве: обычно внедрение идёт за счёт инвестиций в компанию."
        ),
        "ai_scope": (
            "Сейчас автоматизируем: первичку, банковские выписки, акты сверки, тикетинг и отчётность.\n"
            "Система развивается ежемесячно — новые модули и интеграции добавляются автоматически."
        ),
        "changes_clients": (
            "Для клиентов и контрагентов становится быстрее и удобнее:\n"
            "✅ Быстрее обработка документов\n✅ Меньше ошибок\n✅ Омниканальный приём обращений (мессенджеры/портал/email).\n\n"
            "При этом бренд не меняется, договоры не переоформляются."
        ),
        "changes_team": (
            "Команда остаётся с вами. Вы управляете наймом и увольнением.\n"
            "Что меняется: меньше рутины, больше сложных задач и консалтинга, возможна оптимизация нагрузки."
        ),
        "legal_structure": (
            "Основные документы:\n"
            "📜 Акционерное соглашение\n📋 Корпоративный договор\n\n"
            "Что защищает вас: право вето на ключевые решения, прозрачная дивидендная политика, "
            "право первого отказа при продаже доли."
        ),
        "legal_exit": (
            "Механизм выхода фиксируется заранее в соглашении.\n"
            "Обычно доступны: обратный выкуп, продажа третьему лицу с ROFR у AIVEL, совместный выход на пике стоимости."
        ),
    }


def format_mln_range(min_savings_rub: int, max_savings_rub: int) -> str:
    min_mln = round(min_savings_rub / 1_000_000)
    max_mln = round(max_savings_rub / 1_000_000)
    if max_mln < min_mln:
        max_mln = min_mln
    return f"{min_mln}-{max_mln} млн ₽/год"


def format_rub(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ")


async def ask_precise_standardization_question(message: Message):
    await message.answer(
        "5️⃣ Насколько стандартизированы ваши процессы?\n"
        "“При высокой стандартизации вы достигнете результатов на 30% быстрее”\n\n"
        "Выберите вариант ответа:\n"
        "• Высокая стандартизация: есть регламенты, чек-листы, единая методология для всех бухгалтеров\n"
        "• Средняя стандартизация: базовые стандарты есть, но много ручной работы и решений “на месте”\n"
        "• Низкая стандартизация: каждый бухгалтер работает по-своему, процессы не описаны\n",
        parse_mode="HTML",
        reply_markup=simulate_plus3_standardization_keyboard(),
    )


async def send_express_result(message: Message, state: FSMContext):
    data = await state.get_data()
    accountants = int(data["express_accountants"])
    salary = int(data["express_salary"])
    result = calculate_express_operation_savings(accountants, salary)

    text = (
        "🎯 <b>Ваши результаты с Aivel:</b>\n\n"
        "Шаги расчёта через 6 месяцев и через 12 месяцев\n\n"
        "1. <b>Число высвобождаемых бухгалтеров</b>\n"
        f"• через 6 месяцев: <b>{result['released_6']}</b>\n"
        f"• через 12 месяцев: <b>{result['released_12']}</b>\n\n"
        "2. <b>Сохраняемая месячная зарплатная масса</b>\n"
        f"• через 6 месяцев: <b>{format_rub(result['payroll_saved_6'])} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(result['payroll_saved_12'])} ₽ в месяц</b>\n\n"
        "3. <b>Новая стоимость операций на базе искусственного интеллекта</b>\n"
        f"• через 6 месяцев: <b>{format_rub(result['ai_cost_6'])} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(result['ai_cost_12'])} ₽ в месяц</b>\n\n"
        "4. <b>Чистая экономия в месяц</b>\n"
        f"• через 6 месяцев: <b>{format_rub(result['net_6'])} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(result['net_12'])} ₽ в месяц</b>\n\n"
        "⚠️ Это быстрая прикидка экономии на коленке. Для точного расчёта пройдите детальную оценку.\n"
        "Дисклеймер: стоимость услуг AIVEL в среднем составляет 1/5 от операций, "
        "основанных на ручном труде; данный расчёт не является коммерческим предложением, "
        "а представляет собой оценку эффекта от внедрения технологического комплекса AIVEL TECH SUITE."
    )

    user_id = data.get("db_user_id")
    if user_id:
        await save_funnel_fields(
            int(user_id),
            accountants_count=accountants,
            avg_salary=salary,
            express_saving_6=result["net_6"],
            express_saving_12=result["net_12"],
        )
        await add_event(
            int(user_id),
            "simulate_express_completed",
            f"accountants={accountants};salary={salary};net6={format_rub(result['net_6'])};net12={format_rub(result['net_12'])}",
        )

    await state.update_data(simulate_screen="express_result")
    await state.set_state(SimulateFlow.mode_select)
    await message.answer(text, parse_mode="HTML", reply_markup=simulate_results_keyboard())


def find_excel_template() -> Path | None:
    xlsx_candidates = sorted(PROJECT_ROOT.rglob("*.xlsx"))
    if not xlsx_candidates:
        return None

    preferred = [path for path in xlsx_candidates if "aivel" in path.name.lower() or "calculator" in path.name.lower()]
    return preferred[0] if preferred else xlsx_candidates[0]


def is_excel_filename(filename: str | None) -> bool:
    if not filename:
        return False
    lowered = filename.lower()
    return lowered.endswith(".xlsx") or lowered.endswith(".xls") or lowered.endswith(".xlsm")


async def send_simulate_mode_menu(target: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(SimulateFlow.mode_select)

    if isinstance(target, CallbackQuery):
        await target.message.answer(
            SIMULATE_MODE_TEXT,
            parse_mode="HTML",
            reply_markup=simulate_mode_keyboard(),
        )
        await target.answer()
        return

    await target.answer(
        SIMULATE_MODE_TEXT,
        parse_mode="HTML",
        reply_markup=simulate_mode_keyboard(),
    )


def is_simulate_start_locked(user_id: int) -> bool:
    locked_until = SIMULATE_START_LOCKS.get(user_id)
    if locked_until is None:
        return False
    if datetime.utcnow() >= locked_until:
        SIMULATE_START_LOCKS.pop(user_id, None)
        return False
    return True


def lock_simulate_start(user_id: int) -> None:
    SIMULATE_START_LOCKS[user_id] = datetime.utcnow() + timedelta(seconds=SIMULATE_START_LOCK_SECONDS)


async def send_valuation_mode_menu(target: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ValuationFlow.mode_select)

    text = (
        "Ваша фирма 2.0 — это не продажа бизнеса. Это апгрейд.\n"
        "Мы покажем, как партнёрство с AIVEL может изменить экономику вашей фирмы: "
        "больше прибыли, автоматизация рутины и капитал для роста.\n"
        "Выберите, с чего начать:"
    )

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=valuation_mode_keyboard())
        await target.answer()
        return

    await target.answer(text, reply_markup=valuation_mode_keyboard())


async def ensure_simulate_consent(callback: CallbackQuery, state: FSMContext) -> bool:
    return True


async def return_to_base_state(message: Message, state: FSMContext, text: str):
    await state.clear()
    await message.answer(text, reply_markup=persistent_main_keyboard())


def is_personal_data_complete(personal_data: dict[str, str]) -> bool:
    website = personal_data.get("company_website", "").strip().lower()
    required_filled = all(
        [
            personal_data.get("contact_name", "").strip(),
            personal_data.get("contact_email", "").strip(),
            personal_data.get("contact_phone", "").strip(),
            personal_data.get("company", "").strip(),
        ]
    )
    return required_filled and bool(website or website == NO_SITE_MARKER)


async def delete_message_safe(message: Message):
    try:
        await message.delete()
    except TelegramBadRequest:
        return 


async def start_meeting_booking(message: Message, state: FSMContext):
    if not calendly_is_configured():
        await message.answer(
            "Calendly пока не настроен. Проверьте CALENDLY_API_TOKEN и CALENDLY_EVENT_TYPE_URI.",
            reply_markup=persistent_main_keyboard(),
        )
        await state.clear()
        return

    await state.clear()
    await state.set_state(MeetingBookingFlow.waiting_email)
    await message.answer(
        "📅 Запись на встречу через Calendly.\n\n"
        "Отправьте, пожалуйста, ваш email, чтобы мы могли забронировать слот.",
        reply_markup=meeting_waiting_keyboard(),
    )


def format_slot_label(slot_dt: datetime) -> str:
    return slot_dt.strftime("%H:%M")


async def send_excel_and_wait_for_user(callback: CallbackQuery, state: FSMContext):
    excel_path = find_excel_template()
    if excel_path is None:
        await callback.message.answer(SIMULATE_PRO_MISSING_TEXT)
        await callback.answer("Excel-файл пока не найден", show_alert=True)
        return

    await callback.message.answer(SIMULATE_PRO_TEXT)
    await callback.message.answer_document(
        document=FSInputFile(excel_path),
        caption="📥 Excel-опросник для профессиональной оценки",
    )
    user_id = await get_db_user_id(callback)
    await save_funnel_fields(user_id, file_downloaded=True)
    await add_event(user_id, "simulate_pro_excel_sent", excel_path.name)
    await state.set_state(SimulateFlow.precise_wait_excel)
    await callback.message.answer(WAIT_FILE_TEXT, reply_markup=simulate_deep_wait_keyboard())
    await callback.answer()


async def open_tool_flow(message_or_callback: Message | CallbackQuery, state: FSMContext, tool_name: str):
    user_id = await get_db_user_id(message_or_callback)
    await add_event(user_id, "tool_open_requested", tool_name)

    if tool_name == "simulate":
        await send_simulate_mode_menu(message_or_callback, state)
        target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
        await target.answer("Управление инструментом:", reply_markup=tool_navigation_keyboard())
        return

    if tool_name == "valuation":
        await send_valuation_mode_menu(message_or_callback, state)
        target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
        await target.answer("Управление инструментом:", reply_markup=tool_navigation_keyboard())
        return

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(TOOL_PLACEHOLDER_TEXT, reply_markup=persistent_main_keyboard())
        await message_or_callback.answer()
        return

    await message_or_callback.answer(TOOL_PLACEHOLDER_TEXT, reply_markup=persistent_main_keyboard())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    await state.clear()
    await add_event(user_id, "start")
    await send_onboarding_complete(message)


@router.message(F.text.in_({"Меню", "Меню бота"}))
async def open_menu(message: Message, state: FSMContext):
    await show_main_menu(message, state)


@router.message((StateFilter(*SimulateFlow.__all_states__, *ValuationFlow.__all_states__, *MeetingBookingFlow.__all_states__)), F.text == "🏠 В меню")
async def tool_nav_home(message: Message, state: FSMContext):
    await show_main_menu(message, state)


@router.message(StateFilter(*SupportProgramFlow.__all_states__), F.text.in_({"🏠 В Меню", "🏠 В меню"}))
async def support_program_home(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    await save_funnel_fields(user_id, support_program_registered=False)
    await show_main_menu(message, state)


@router.message(StateFilter(*SupportProgramFlow.__all_states__), F.text == "↩️ Назад")
async def support_program_back(message: Message, state: FSMContext):
    current_state = await state.get_state()
    user_id = await get_db_user_id(message)

    if current_state == SupportProgramFlow.contact_name.state:
        await save_funnel_fields(user_id, support_program_registered=False)
        await show_main_menu(message, state)
        return
    if current_state == SupportProgramFlow.contact_phone.state:
        await state.set_state(SupportProgramFlow.contact_name)
        await message.answer("Введите ваше имя:", reply_markup=support_program_navigation_keyboard())
        return
    if current_state == SupportProgramFlow.contact_email.state:
        await state.set_state(SupportProgramFlow.contact_phone)
        await message.answer("Введите ваш номер телефона:", reply_markup=support_program_navigation_keyboard())
        return
    if current_state == SupportProgramFlow.business_stage.state:
        await state.set_state(SupportProgramFlow.contact_email)
        await message.answer("Введите ваш адрес электронной почты:", reply_markup=support_program_navigation_keyboard())
        return

    await show_main_menu(message, state)


@router.message(StateFilter(*SupportProgramFlow.__all_states__), F.text.in_({"❌ Отменить", "Отменить"}))
async def support_program_cancel(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    await save_funnel_fields(user_id, support_program_registered=False)
    await return_to_base_state(message, state, "Регистрация в программе поддержки отменена.")


@router.message((StateFilter(*SimulateFlow.__all_states__, *ValuationFlow.__all_states__, *MeetingBookingFlow.__all_states__)), F.text == "❌ Отменить")
async def tool_nav_cancel(message: Message, state: FSMContext):
    await return_to_base_state(message, state, THANKS_TOOL_TEXT)


@router.message((StateFilter(*SimulateFlow.__all_states__, *ValuationFlow.__all_states__, *MeetingBookingFlow.__all_states__)), F.text == "⏭ Пропустить")
async def tool_nav_skip(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == SimulateFlow.express_accountants.state:
        await state.update_data(express_accountants=DEFAULT_EXPRESS_ACCOUNTANTS)
        await state.set_state(SimulateFlow.express_salary)
        await message.answer(
            "2️⃣ Средняя зарплата бухгалтера (₽/мес, включая налоги)?\n\n"
            f"Например: {DEFAULT_EXPRESS_SALARY}",
        )
        return
    if current_state == SimulateFlow.express_salary.state:
        await state.update_data(express_salary=DEFAULT_EXPRESS_SALARY)
        await send_express_result(message, state)
        return
    if current_state == ValuationFlow.express_revenue.state:
        user_id = await get_db_user_id(message)
        cancel_valuation_idle_task(user_id)
        await state.update_data(valuation_revenue_mln=DEFAULT_VALUATION_REVENUE_MLN)
        await save_funnel_fields(user_id, valuation_revenue_mln=DEFAULT_VALUATION_REVENUE_MLN)
        await state.set_state(ValuationFlow.express_share)
        await message.answer(
            f"Приняли значение из примера: {format_mln(DEFAULT_VALUATION_REVENUE_MLN)} млн руб.\n\n"
            "<b>Q2: Какая доля выручки приходится на базовый бухгалтерский аутсорсинг? (%)</b>\n\n"
            "Это обработка первичных документов, сверки и банк-клиент. Без учёта аудита, консалтинга и прочих услуг.",
            parse_mode="HTML",
            reply_markup=valuation_share_keyboard(),
        )
        return
    if current_state == ValuationFlow.express_share.state:
        user_id = await get_db_user_id(message)
        cancel_valuation_idle_task(user_id)
        share = VALUATION_SHARE_MAP[DEFAULT_VALUATION_SHARE_OPTION]
        await state.update_data(valuation_share_percent=share)
        await save_funnel_fields(user_id, valuation_share_percent=share)
        await state.set_state(ValuationFlow.express_profitability)
        await message.answer(
            "Приняли среднее значение: 60–80%.\n\n"
            "<b>Q3: Какая коммерческая маржа (прибыльность) на базовых бухгалтерских услугах (P)?</b>\n\n"
            "Это прибыль от базовой бухгалтерии ÷ выручка от базовой бухгалтерии.",
            parse_mode="HTML",
            reply_markup=valuation_profitability_keyboard(),
        )
        return
    if current_state == ValuationFlow.express_profitability.state:
        user_id = await get_db_user_id(message)
        cancel_valuation_idle_task(user_id)
        profitability = VALUATION_PROFITABILITY_MAP[DEFAULT_VALUATION_PROFITABILITY_OPTION]
        data = await state.get_data()
        revenue_mln = float(data.get("valuation_revenue_mln", DEFAULT_VALUATION_REVENUE_MLN))
        profit_mln = revenue_mln * (profitability / 100)
        valuation_mln = round(profit_mln * VALUATION_MULTIPLE, 1)
        profit_mln_rounded = round(profit_mln, 1)

        await state.update_data(
            valuation_profitability_percent=profitability,
            valuation_profit_mln=profit_mln_rounded,
            valuation_result_mln=valuation_mln,
        )
        await save_funnel_fields(
            user_id,
            valuation_profitability_percent=profitability,
            valuation_profit_mln=profit_mln_rounded,
            valuation_result_mln=valuation_mln,
        )
        await add_event(
            user_id,
            "valuation_express_completed",
            (
                f"revenue_mln={revenue_mln};share={data.get('valuation_share_percent')};"
                f"profitability={profitability};profit_mln={profit_mln_rounded};valuation_mln={valuation_mln};skipped_profitability=true"
            ),
        )

        await state.set_state(ValuationFlow.express_continue)
        await message.answer(
            "Приняли среднее значение: я не знаю / 25%.\n\n"
            "Оценка стоимости вашей фирмы\n"
            f"{profit_mln_rounded:.1f} × {VALUATION_MULTIPLE:.1f} = {valuation_mln:.1f} млн руб.\n"
            "— стандарт для бухгалтерских практик\n\n"
            "Есть несколько важных нюансов, которые нужно уточнить. "
            "Вы согласны ответить на ещё несколько вопросов, чтобы быть точнее и учесть важные моменты?",
            reply_markup=valuation_continue_keyboard(),
        )
        return
    if current_state == ValuationFlow.express_continue.state:
        user_id = await get_db_user_id(message)
        cancel_valuation_idle_task(user_id)
        await state.set_state(ValuationFlow.precise_clients_total)
        await message.answer(
            "Приняли среднее действие: продолжить уточнение.\n\n"
            "Отлично! Теперь несколько вопросов о вашем клиентском портфеле и команде. "
            "Это поможет нам понять, как ИИ-автоматизация и инвестиции лучше всего впишутся именно в вашу фирму.\n\n"
            "Ещё 5 вопросов — займёт пару минут 👇\n\n"
            "<b>Q4: Сколько у вас активных клиентов?</b>\n\n"
            "Считайте только тех, кто получает услуги по базовой бухгалтерии. "
            "Напишите одно число (например: 50, 250, 500).",
            parse_mode="HTML",
        )
        return
    if current_state == SimulateFlow.precise_advisory.state:
        await state.update_data(plus3_advisory="10_20")
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), advisory_band="10_20")
        await state.set_state(SimulateFlow.precise_clients)
        await message.answer(
            "Приняли среднее значение: 10–20%.\n\n"
            "4️⃣ Количество активных клиентов?\n\n"
            "Напишите свой ответ сообщением.\n"
            "Например: 120",
            parse_mode="HTML",
        )
        return
    if current_state == SimulateFlow.precise_standardization.state:
        await state.update_data(plus3_standardization="medium")
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), standardization_level="medium")
        await state.set_state(SimulateFlow.precise_automation)
        await message.answer(
            "Приняли среднее значение: средняя стандартизация.\n\n"
            "6️⃣ Используете ли вы сейчас какие-то инструменты автоматизации?\n\n",
            parse_mode="HTML",
            reply_markup=simulate_plus3_automation_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_automation.state:
        await state.update_data(plus3_automation="partial")
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), automation_level="partial")
        await state.set_state(SimulateFlow.precise_margin)
        await message.answer(
            "Приняли среднее значение: частичная автоматизация.\n\n"
            "7️⃣ Текущая валовая маржа (%)?\n\n"
            "Напишите свой ответ сообщением.\n"
            "Например: 35",
            parse_mode="HTML",
        )
        return
    if current_state == SimulateFlow.precise_clients.state:
        await state.update_data(precise_clients=120)
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), active_clients_count=120)
        await state.set_state(SimulateFlow.precise_contacts)
        await message.answer(
            "Поделитесь с нами вашими контактными данными (Ваше имя, Email, Телефон, Компания, Вебсайт)\n",
            parse_mode="HTML",
            reply_markup=simulate_contacts_choice_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_contacts.state:
        if (await state.get_data()).get("force_full_contacts", False):
            await message.answer("В этом сценарии пропуск недоступен.")
            return
        await state.update_data(precise_contacts="")
        await state.set_state(SimulateFlow.precise_standardization)
        await ask_precise_standardization_question(message)
        return
    if current_state == SimulateFlow.precise_margin.state:
        await state.update_data(precise_margin=35)
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), margin_percent=35)
        await finalize_precise_assessment(message, state)
        return
    if current_state == SimulateFlow.precise_growth.state:
        await state.update_data(post_growth="normal")
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), growth_band="normal")
        await state.set_state(SimulateFlow.precise_mna)
        await message.answer(
            "Приняли среднее значение: обычный рост +5–20%.\n\n"
            "Рассматриваете ли вы M&A / привлечение инвестиций?",
            reply_markup=simulate_mna_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_mna.state:
        await state.update_data(post_mna="no")
        user_id = (await state.get_data()).get("db_user_id")
        if user_id:
            await save_funnel_fields(int(user_id), mna_interest="no")
        await state.set_state(SimulateFlow.precise_wait_excel)
        await message.answer(
            "Приняли среднее значение: нет.\n\n"
            "🎯 Серьёзно рассматриваете внедрение? Загрузите Excel — получите полный бизнес-кейс от нашей команды.",
            reply_markup=simulate_deep_assessment_keyboard(),
        )
        return
    await message.answer("На этом шаге пропуск не требуется.")


@router.message((StateFilter(*SimulateFlow.__all_states__, *ValuationFlow.__all_states__, *MeetingBookingFlow.__all_states__)), F.text == "⬅️ Назад")
async def tool_nav_back(message: Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()

    if current_state == SimulateFlow.mode_select.state:
        if data.get("simulate_screen") == "express_result":
            await state.set_state(SimulateFlow.express_salary)
            await message.answer(
                "Вернули вас к последнему вопросу экспресс-оценки.\n"
                "Введите среднюю зарплату бухгалтера заново — после этого я пересчитаю оценку и сохраню изменения.\n\n"
                f"Например: {DEFAULT_EXPRESS_SALARY}",
            )
            return
        await show_main_menu(message, state)
        return
    if current_state == SimulateFlow.express_accountants.state:
        await restart_simulate_flow(message, state)
        return
    if current_state == SimulateFlow.express_salary.state:
        await state.set_state(SimulateFlow.express_accountants)
        await message.answer(
            "1️⃣ Сколько у вас бухгалтеров задействовано в операциях?\n"
            f"Например: {DEFAULT_EXPRESS_ACCOUNTANTS}"
        )
        return
    if current_state == SimulateFlow.precise_advisory.state:
        await state.set_state(SimulateFlow.mode_select)
        await message.answer(SIMULATE_MODE_TEXT, parse_mode="HTML", reply_markup=simulate_mode_keyboard())
        return
    if current_state == SimulateFlow.precise_contacts.state:
        await state.set_state(SimulateFlow.precise_clients)
        await message.answer("4️⃣ Сколько у вас активных клиентов?\nНапишите число или нажмите «Пропустить».")
        return
    if current_state == SimulateFlow.precise_contact_name.state:
        await state.set_state(SimulateFlow.precise_contacts)
        await message.answer(
            "Поделитесь с нами вашими контактными данными (Ваше имя, Email, Телефон, Компания, Вебсайт)\n",
            parse_mode="HTML",
            reply_markup=simulate_contacts_choice_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_contact_email.state:
        await state.set_state(SimulateFlow.precise_contact_name)
        await message.answer("Ваше имя?")
        return
    if current_state == SimulateFlow.precise_contact_phone.state:
        await state.set_state(SimulateFlow.precise_contact_email)
        await message.answer("Ваш email?")
        return
    if current_state == SimulateFlow.precise_contact_company.state:
        await state.set_state(SimulateFlow.precise_contact_phone)
        await message.answer("Ваш телефон?")
        return
    if current_state == SimulateFlow.precise_contact_website.state:
        await state.set_state(SimulateFlow.precise_contact_company)
        await message.answer("Название компании?")
        return
    if current_state == SimulateFlow.precise_standardization.state:
        await state.set_state(SimulateFlow.precise_contacts)
        await message.answer(
            "Поделитесь с нами вашими контактными данными (Ваше имя, Email, Телефон, Компания, Вебсайт)\n",
            parse_mode="HTML",
            reply_markup=simulate_contacts_choice_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_automation.state:
        await state.set_state(SimulateFlow.precise_standardization)
        await ask_precise_standardization_question(message)
        return
    if current_state == SimulateFlow.precise_margin.state:
        await state.set_state(SimulateFlow.precise_automation)
        await message.answer(
            "6️⃣ Используете ли вы сейчас какие-то инструменты автоматизации?\n\n",
            parse_mode="HTML",
            reply_markup=simulate_plus3_automation_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_growth.state:
        await state.set_state(SimulateFlow.precise_margin)
        await message.answer("7️⃣ Текущая валовая маржа (%)?\n\nНапишите свой ответ сообщением.\nНапример: 35")
        return
    if current_state == SimulateFlow.precise_mna.state:
        await state.set_state(SimulateFlow.precise_growth)
        await message.answer(
            "Планируете ли вы рост в ближайшие 12-24 месяца?",
            reply_markup=simulate_growth_keyboard(),
        )
        return
    if current_state == SimulateFlow.precise_wait_excel.state:
        await state.set_state(SimulateFlow.precise_mna)
        await message.answer(
            "Рассматриваете ли вы M&A / привлечение инвестиций?",
            reply_markup=simulate_mna_keyboard(),
        )
        return

    if current_state == ValuationFlow.mode_select.state:
        await show_main_menu(message, state)
        return
    if current_state == ValuationFlow.express_revenue.state:
        await restart_valuation_flow(message, state)
        return
    if current_state == ValuationFlow.express_share.state:
        await state.set_state(ValuationFlow.express_revenue)
        await message.answer(
            "<b>Q1: Какая годовая выручка вашей фирмы? (млн руб.)</b>\n\n"
            "Просто напишите число, например: 30",
            parse_mode="HTML",
        )
        return
    if current_state == ValuationFlow.express_profitability.state:
        await state.set_state(ValuationFlow.express_share)
        await message.answer(
            "<b>Q2: Какая доля выручки приходится на базовый бухгалтерский аутсорсинг? (%)</b>\n\n"
            "Это обработка первичных документов, сверки и банк-клиент. Без учёта аудита, консалтинга и прочих услуг.",
            parse_mode="HTML",
            reply_markup=valuation_share_keyboard(),
        )
        return
    if current_state == ValuationFlow.express_continue.state:
        await state.set_state(ValuationFlow.express_profitability)
        await message.answer(
            "<b>Q3: Какая коммерческая маржа (прибыльность) на базовых бухгалтерских услугах (P)?</b>\n\n"
            "Это прибыль от базовой бухгалтерии ÷ выручка от базовой бухгалтерии.",
            parse_mode="HTML",
            reply_markup=valuation_profitability_keyboard(),
        )
        return
    if current_state == ValuationFlow.precise_clients_total.state:
        await state.set_state(ValuationFlow.express_continue)
        await message.answer(
            "Есть несколько важных нюансов, которые нужно уточнить. "
            "Вы согласны ответить на ещё несколько вопросов, чтобы быть точнее и учесть важные моменты?",
            reply_markup=valuation_continue_keyboard(),
        )
        return
    if current_state == ValuationFlow.precise_clients_key.state:
        await state.set_state(ValuationFlow.precise_clients_total)
        await message.answer("<b>Q4: Сколько у вас активных клиентов?</b>", parse_mode="HTML")
        return
    if current_state == ValuationFlow.precise_top5_share.state:
        await state.set_state(ValuationFlow.precise_clients_key)
        await message.answer(
            "<b>Q5: Сколько клиентов приносят основную часть вашей выручки от базовой бухгалтерии?</b>\n\n"
            "Напишите одно число (например: 5, 15, 40).",
            parse_mode="HTML",
        )
        return
    if current_state == ValuationFlow.precise_headcount.state:
        await state.set_state(ValuationFlow.precise_top5_share)
        await message.answer(
            "<b>Q6: Какую долю выручки от базовой бухгалтерии приносят ваши 5 крупнейших клиентов?</b>",
            parse_mode="HTML",
            reply_markup=valuation_q6_share_keyboard(),
        )
        return
    if current_state == ValuationFlow.precise_automation_level.state:
        await state.set_state(ValuationFlow.precise_headcount)
        await message.answer(
            "<b>Q7: Сколько бухгалтеров занято на базовых операциях?</b>\n\n"
            "Напишите одно число (например: 5, 15, 40).",
            parse_mode="HTML",
        )
        return
    if current_state == ValuationFlow.precise_automation_tools.state:
        await state.set_state(ValuationFlow.precise_automation_level)
        await message.answer(
            "<b>Q8: Используете ли вы инструменты автоматизации в бухгалтерии?</b>\n\n"
            "Выберите вариант ответа:",
            parse_mode="HTML",
            reply_markup=valuation_q8_automation_level_keyboard(),
        )
        return
    if current_state == ValuationFlow.precise_post_result.state:
        await restart_valuation_flow(message, state)
        return

    if current_state == MeetingBookingFlow.waiting_date.state:
        await state.set_state(MeetingBookingFlow.waiting_email)
        await message.answer("Отправьте, пожалуйста, ваш email для записи на встречу.")
        return
    if current_state == MeetingBookingFlow.waiting_custom_time.state:
        selected_date = data.get("meeting_date")
        if selected_date:
            await state.set_state(MeetingBookingFlow.waiting_date)
            year, month = map(int, selected_date[:7].split("-"))
            await message.answer("Выберите дату созвона:", reply_markup=meeting_calendar_keyboard(year, month))
            return
    if current_state == MeetingBookingFlow.waiting_email.state:
        await show_main_menu(message, state)
        return

    await message.answer("Эта кнопка «Назад» уже неактуальна. Показываю главное меню 👇")
    await show_main_menu(message, state)

@router.message(F.text == "Калькулятор экономии")
async def open_simulate_from_keyboard(message: Message, state: FSMContext):
    await open_tool_flow(message, state, "simulate")


@router.message(F.text.in_({"Сделка и рост", "Оценка стоимости фирмы (скоро)"}))
async def open_valuation_from_keyboard(message: Message, state: FSMContext):
    await open_tool_flow(message, state, "valuation")


@router.callback_query(F.data == "tool:simulate")
async def open_simulate_from_menu(callback: CallbackQuery, state: FSMContext):
    await open_tool_flow(callback, state, "simulate")


@router.callback_query(F.data == "gift:chat_analyzer")
async def send_chat_analyzer_gift(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)

    if not CHAT_ANALYZER_PDF_PATH.exists():
        await add_event(user_id, "chat_analyzer_gift_missing")
        await callback.answer("PDF-файл пока не найден", show_alert=True)
        return

    await callback.message.answer_document(
        document=FSInputFile(CHAT_ANALYZER_PDF_PATH),
        caption="🎁 Анализатор клиентских чатов в Битрикс24 и Telegram",
    )
    await add_event(user_id, "chat_analyzer_gift_sent", CHAT_ANALYZER_PDF_PATH.name)
    await callback.message.answer(CHAT_ANALYZER_GIFT_TEXT)
    await callback.answer()


@router.callback_query(F.data == "support_program:join")
async def support_program_join(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    await state.clear()
    await save_funnel_fields(user_id, support_program_registered=True)
    await state.update_data(db_user_id=user_id)
    await state.set_state(SupportProgramFlow.contact_name)
    await add_event(user_id, "support_program_join_clicked")
    await callback.message.answer(
        SUPPORT_PROGRAM_INTRO_TEXT,
        parse_mode="HTML",
        reply_markup=support_program_navigation_keyboard(),
    )
    await callback.message.answer("Введите ваше имя:")
    await callback.answer()


@router.message(SupportProgramFlow.contact_name, F.text)
async def support_program_contact_name(message: Message, state: FSMContext):
    name = " ".join(message.text.strip().split())
    if not is_valid_support_name(name):
        await message.answer("Пожалуйста, введите имя текстом, без цифр. Например: Ян или Мария")
        return

    user_id = (await state.get_data()).get("db_user_id") or await get_db_user_id(message)
    await state.update_data(db_user_id=user_id, contact_name=name)
    await save_funnel_fields(int(user_id), contact_name=name)
    await state.set_state(SupportProgramFlow.contact_phone)
    await message.answer("Введите ваш номер телефона:", reply_markup=support_program_navigation_keyboard())


@router.message(SupportProgramFlow.contact_phone, F.text)
async def support_program_contact_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not is_valid_support_phone(phone):
        await message.answer(
            "Пожалуйста, введите корректный номер телефона: 10–15 цифр, можно с + и пробелами.\n"
            "Например: +7 999 123-45-67"
        )
        return

    user_id = (await state.get_data()).get("db_user_id") or await get_db_user_id(message)
    await state.update_data(db_user_id=user_id, contact_phone=phone)
    await save_funnel_fields(int(user_id), contact_phone=phone)
    await state.set_state(SupportProgramFlow.contact_email)
    await message.answer("Введите ваш адрес электронной почты:", reply_markup=support_program_navigation_keyboard())


@router.message(SupportProgramFlow.contact_email, F.text)
async def support_program_contact_email(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    if not is_valid_support_email(email):
        await message.answer("Пожалуйста, введите корректный email. Например: name@company.com")
        return

    user_id = (await state.get_data()).get("db_user_id") or await get_db_user_id(message)
    await state.update_data(db_user_id=user_id, contact_email=email)
    await save_funnel_fields(int(user_id), contact_email=email)
    await state.set_state(SupportProgramFlow.business_stage)
    await message.answer(
        "Выберите подходящий вариант:",
        reply_markup=support_program_business_stage_keyboard(),
    )


@router.callback_query(SupportProgramFlow.business_stage, F.data.startswith("support_program:stage:"))
async def support_program_business_stage(callback: CallbackQuery, state: FSMContext):
    stage = (callback.data or "").split(":")[-1]
    if stage not in {"owner", "want_to_open"}:
        await callback.answer("Неизвестный вариант", show_alert=True)
        return

    user_id = (await state.get_data()).get("db_user_id") or await get_db_user_id(callback)
    await save_funnel_fields(int(user_id), business_stage=stage, support_program_registered=True)
    await add_event(user_id, "support_program_registered", stage)
    await state.clear()
    await callback.message.answer(SUPPORT_PROGRAM_FINAL_TEXT, parse_mode="HTML", reply_markup=persistent_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "tool:valuation")
async def open_valuation_from_menu(callback: CallbackQuery, state: FSMContext):
    await open_tool_flow(callback, state, "valuation")


@router.callback_query(F.data == "valuation:menu:faq")
async def open_valuation_faq_from_main_menu(callback: CallbackQuery):
    await callback.answer()
    await send_valuation_faq_topics(callback.message)


@router.callback_query(F.data == "stub:book_meeting")
async def book_meeting(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Откройте Calendly по кнопке ниже 👇",
        reply_markup=calendly_meeting_keyboard(),
        disable_web_page_preview=True,
    )
    await callback.message.answer(
        "Вам удалось записаться на встречу?",
        reply_markup=meeting_registration_check_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "stub:events")
async def show_events(callback: CallbackQuery):
    await callback.answer()
    loading_message = await callback.message.answer("⏳ Собираем информацию о ближайших мероприятиях...")

    try:
        events = fetch_events(
            spreadsheet_id=str(GOOGLE_SHEETS_SPREADSHEET_ID or ""),
            api_key=str(GOOGLE_SHEETS_API_KEY or ""),
            sheet_range=GOOGLE_SHEETS_RANGE,
        )
    except EventsConfigError:
        await delete_message_safe(loading_message)
        await callback.message.answer(
            "⚠️ Раздел мероприятий временно недоступен: не настроен доступ к Google Sheets."
        )
        return
    except EventsRequestError as exc:
        await delete_message_safe(loading_message)
        await callback.message.answer(f"⚠️ Не удалось получить данные мероприятий. {exc}")
        return

    await delete_message_safe(loading_message)
    await callback.message.answer(
        format_events_message(events),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "meeting:external:yes")
async def meeting_external_confirmed(callback: CallbackQuery, state: FSMContext):
    await delete_message_safe(callback.message)
    user_id = await get_db_user_id(callback)
    await save_funnel_fields(user_id, meeting_booked=True)
    await add_event(user_id, "meeting_external_confirmed", "yes")
    await return_to_base_state(callback.message, state, "Отлично! Спасибо за регистрацию на встречу 🙌")
    await callback.answer()


@router.callback_query(F.data == "meeting:external:no")
async def meeting_external_declined(callback: CallbackQuery, state: FSMContext):
    await delete_message_safe(callback.message)
    user_id = await get_db_user_id(callback)
    await add_event(user_id, "meeting_external_confirmed", "no")
    await return_to_base_state(callback.message, state, "Хорошо, вернули вас в главное меню.")
    await callback.answer()


@router.callback_query(F.data == "meeting:noop")
async def meeting_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(
    MeetingBookingFlow.waiting_email,
    F.data == "meeting:back",
)
@router.callback_query(
    MeetingBookingFlow.waiting_date,
    F.data == "meeting:back",
)
@router.callback_query(
    MeetingBookingFlow.waiting_custom_time,
    F.data == "meeting:back",
)
@router.callback_query(SimulateFlow.precise_wait_excel, F.data == "meeting:back")
async def meeting_back(callback: CallbackQuery, state: FSMContext):
    await return_to_base_state(callback.message, state, "Спасибо, вернёмся к этому позже.")
    await callback.answer()


@router.message(MeetingBookingFlow.waiting_email, F.text)
async def meeting_email_step(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    if not MEETING_EMAIL_RE.match(email):
        await message.answer("Пожалуйста, отправьте корректный email. Пример: name@company.com")
        return

    now = datetime.now(ZoneInfo(MEETING_TIMEZONE))
    await state.update_data(meeting_email=email)
    user_id = await get_db_user_id(message)
    await save_funnel_fields(user_id, contact_email=email)
    await state.set_state(MeetingBookingFlow.waiting_date)
    await message.answer(
        "Выберите дату созвона:",
        reply_markup=meeting_calendar_keyboard(now.year, now.month),
    )


@router.callback_query(MeetingBookingFlow.waiting_date, F.data.startswith("meeting:date:nav:"))
async def meeting_date_nav(callback: CallbackQuery):
    _, _, _, ym = callback.data.split(":")
    year_str, month_str = ym.split("-")
    year, month = int(year_str), int(month_str)
    await callback.message.edit_reply_markup(reply_markup=meeting_calendar_keyboard(year, month))
    await callback.answer()


@router.callback_query(MeetingBookingFlow.waiting_date, F.data.startswith("meeting:date:pick:"))
async def meeting_date_pick(callback: CallbackQuery, state: FSMContext):
    selected = date.fromisoformat(callback.data.split(":")[-1])
    await state.update_data(meeting_date=selected.isoformat())

    try:
        slots = get_available_hour_slots(selected)
    except (CalendlyRequestError, CalendlyNotConfiguredError) as exc:
        await callback.message.answer(f"Не удалось получить слоты Calendly: {exc}")
        await callback.answer()
        return

    first_five = [format_slot_label(slot) for slot in slots[:5]]
    await state.update_data(meeting_slot_candidates=first_five)
    await callback.message.answer(
        "Свободные слоты на выбранную дату:",
        reply_markup=meeting_slots_keyboard(first_five),
    )
    await callback.answer()


@router.callback_query(MeetingBookingFlow.waiting_date, F.data.startswith("meeting:slot:"))
async def meeting_slot_pick(callback: CallbackQuery, state: FSMContext):
    value = callback.data.removeprefix("meeting:slot:")
    if value == "other":
        await state.set_state(MeetingBookingFlow.waiting_custom_time)
        await callback.message.answer(
            "Выберите удобное время:",
            reply_markup=meeting_custom_time_keyboard(),
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected_date = date.fromisoformat(data["meeting_date"])
    hour, minute = map(int, value.split("-") if "-" in value else value.split(":"))
    slot_dt = datetime.combine(selected_date, time(hour, minute), ZoneInfo(MEETING_TIMEZONE))

    try:
        if not is_slot_available(slot_dt):
            await callback.message.answer("Этот слот уже недоступен. Выберите другое время.")
            await callback.answer()
            return

        tg_user = callback.from_user
        invitee_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip() or "Aivel Client"
        booking = book_slot(slot_dt, invitee_name, str(data["meeting_email"]))
    except CalendlyRequestError as exc:
        await callback.message.answer(f"Не удалось забронировать слот: {exc}")
        await callback.answer()
        return

    user_id = await get_db_user_id(callback)
    await save_funnel_fields(user_id, meeting_booked=True)
    await add_event(user_id, "meeting_booked", slot_dt.isoformat())
    await return_to_base_state(
        callback.message,
        state,
        f"✅ Встреча забронирована!\nСсылка: {booking.booking_url}",
    )
    await callback.answer()


@router.callback_query(MeetingBookingFlow.waiting_custom_time, F.data.startswith("meeting:time:"))
async def meeting_custom_time_pick(callback: CallbackQuery, state: FSMContext):
    _, _, hh, mm = callback.data.split(":")
    data = await state.get_data()
    selected_date = date.fromisoformat(data["meeting_date"])
    slot_dt = datetime.combine(selected_date, time(int(hh), int(mm)), ZoneInfo(MEETING_TIMEZONE))

    try:
        if not is_slot_available(slot_dt):
            await callback.message.answer(
                "Слот недоступен. Выберите другое время:",
                reply_markup=meeting_custom_time_keyboard(),
            )
            await callback.answer()
            return

        tg_user = callback.from_user
        invitee_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip() or "Aivel Client"
        booking = book_slot(slot_dt, invitee_name, str(data["meeting_email"]))
    except CalendlyRequestError as exc:
        await callback.message.answer(f"Не удалось забронировать слот: {exc}")
        await callback.answer()
        return

    user_id = await get_db_user_id(callback)
    await save_funnel_fields(user_id, meeting_booked=True)
    await add_event(user_id, "meeting_booked_custom", slot_dt.isoformat())
    await return_to_base_state(
        callback.message,
        state,
        f"✅ Встреча забронирована!\nСсылка: {booking.booking_url}",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stub:"))
async def menu_stub(callback: CallbackQuery):
    await callback.answer("Раздел в разработке. Скоро добавим функционал.", show_alert=True)


@router.callback_query(F.data == "simulate:mode:menu")
async def simulate_mode_menu(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    await send_simulate_mode_menu(callback, state)


@router.callback_query(F.data == "simulate:back")
async def simulate_back_to_main(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    await return_to_base_state(callback.message, state, THANKS_TOOL_TEXT)
    await callback.answer()


@router.callback_query(F.data == "simulate:mode:express")
async def simulate_mode_express(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    if not await ensure_simulate_consent(callback, state):
        return

    user_id = await get_db_user_id(callback)
    if is_simulate_start_locked(user_id):
        await callback.answer("Экспресс-оценка уже запускается…", show_alert=False)
        return
    lock_simulate_start(user_id)

    if await state.get_state() == SimulateFlow.express_accountants.state:
        await callback.answer("Экспресс-оценка уже открыта 👇", show_alert=False)
        return

    await add_event(user_id, "simulate_mode_selected", "express")

    await state.update_data(db_user_id=user_id)
    await state.set_state(SimulateFlow.express_accountants)
    await callback.message.answer(
        "⚡ <b>Экспресс-оценка</b>\n\nОтветьте на 2 простых вопроса.\n\n"
        "1️⃣ Сколько у вас бухгалтеров (чел.) задействовано в выполнении следующих операций:\n"
        "• Обработка входящих запросов и документов\n"
        "• Первичные документы\n"
        "• Акты сверки\n"
        "• Работа с банк-клиентом\n\n"
        "Напишите свой ответ сообщением.\n"
        f"Например: {DEFAULT_EXPRESS_ACCOUNTANTS}",
        parse_mode="HTML",
        
    )
    await callback.answer()


@router.callback_query(F.data == "simulate:mode:precise")
async def simulate_mode_precise(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    if not await ensure_simulate_consent(callback, state):
        return

    user_id = await get_db_user_id(callback)
    await add_event(user_id, "simulate_mode_selected", "precise")

    data = await state.get_data()
    await state.update_data(
        precise_accountants=int(data.get("express_accountants", DEFAULT_EXPRESS_ACCOUNTANTS)),
        precise_salary=int(data.get("express_salary", DEFAULT_EXPRESS_SALARY)),
    )
    await state.set_state(SimulateFlow.precise_advisory)
    await callback.message.answer(
        "✅ <b>Точная оценка</b>\n\n"
        "3️⃣ Какой % клиентов требует нестандартных консультаций / advisory работы?\n"
        "Сложные налоговые кейсы, реструктуризация, M&A-поддержка, специальные отраслевые требования\n\n"
        "Выберите вариант ответа:\n"
        "• Менее 10% — почти все клиенты стандартные\n"
        "• 10-20% — есть несколько сложных клиентов\n"
        "• >20% — заметная доля advisory\n",
        parse_mode="HTML",
        reply_markup=simulate_plus3_advisory_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "simulate:mode:pro")
async def simulate_mode_pro(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    if not await ensure_simulate_consent(callback, state):
        return

    user_id = await get_db_user_id(callback)
    await add_event(user_id, "simulate_mode_selected", "pro")

    await send_excel_and_wait_for_user(callback, state)


@router.callback_query(F.data == "valuation:back")
async def valuation_back_to_main(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await return_to_base_state(callback.message, state, THANKS_TOOL_TEXT)
    await callback.answer()


@router.callback_query(F.data == "valuation:mode:express")
async def valuation_mode_express(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await callback.message.answer(
        "⚡ <b>Экспресс-оценка</b>\n\n"
        "Ответьте на 3 вопроса — и мы мгновенно рассчитаем:\n"
        "• стоимость вашей фирмы\n"
        "• сумму, которую вы получите при сделке\n"
        "• ваш доход за 5 лет с партнёрством и без",
        parse_mode="HTML",
        reply_markup=valuation_intro_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "valuation:mode:excel")
async def valuation_mode_excel(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await callback.answer()
    await callback.message.answer(VALUATION_EXCEL_TEXT, reply_markup=valuation_excel_offer_keyboard())


@router.callback_query(F.data == "valuation:mode:faq")
async def valuation_mode_faq(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await callback.answer()
    await send_valuation_faq_topics(callback.message)


@router.callback_query(F.data == "valuation:express:start")
async def valuation_express_start(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await state.set_state(ValuationFlow.express_revenue)
    await callback.message.answer(
        "<b>Q1: Какая годовая выручка вашей фирмы? (млн руб.)</b>\n\n"
        "Просто напишите число, например: 30",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ValuationFlow.express_revenue, F.text)
async def valuation_express_revenue(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    cancel_valuation_idle_task(user_id)
    revenue = parse_float(message.text)
    if revenue is None:
        await message.answer("Пожалуйста, введите число в миллионах рублей. Например: 30")
        return
    if revenue <= 0:
        await message.answer("Введите положительное число больше нуля.")
        return
    if revenue > VALUATION_RUB_INPUT_THRESHOLD:
        await message.answer(
            "Похоже, вы ввели сумму в рублях. Введите в миллионах — например, 30 означает 30 млн руб."
        )
        return

    await state.update_data(valuation_revenue_mln=revenue)
    await save_funnel_fields(user_id, valuation_revenue_mln=revenue)
    await state.set_state(ValuationFlow.express_share)
    await message.answer(
        "<b>Q2: Какая доля выручки приходится на базовый бухгалтерский аутсорсинг? (%)</b>\n\n"
        "Это обработка первичных документов, сверки и банк-клиент. Без учёта аудита, консалтинга и прочих услуг.",
        parse_mode="HTML",
        reply_markup=valuation_share_keyboard(),
    )


@router.callback_query(ValuationFlow.express_share, F.data.startswith("valuation:share:"))
async def valuation_express_share(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    option = callback.data.removeprefix("valuation:share:")
    if option in VALUATION_LOW_SHARE_OPTIONS:
        await callback.message.answer(
            "Спасибо за ответ!\n"
            "Сейчас мы фокусируемся на фирмах, где базовая бухгалтерия составляет основную часть бизнеса "
            "(от 50% выручки).\n"
            "Но если вы рассматриваете выделение бухгалтерского направления в отдельную структуру — "
            "мы можем обсудить такой вариант с нашим менеджером.\n\n"
            "Это может быть интересно, если:\n"
            "• У вас есть устойчивый поток клиентов на базовую бухгалтерию\n"
            "• Вы хотите сфокусироваться на консалтинге / аудите\n"
            "• Бухгалтерское направление можно выделить без потери клиентов",
            reply_markup=valuation_low_share_keyboard(),
        )
        await callback.answer()
        return

    share = VALUATION_SHARE_MAP.get(option)
    if share is None:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    await state.update_data(valuation_share_percent=share)
    await save_funnel_fields(user_id, valuation_share_percent=share)
    await state.set_state(ValuationFlow.express_profitability)
    await callback.message.answer(
        "<b>Q3: Какая коммерческая маржа (прибыльность) на базовых бухгалтерских услугах (P)?</b>\n\n"
        "Это прибыль от базовой бухгалтерии ÷ выручка от базовой бухгалтерии.",
        parse_mode="HTML",
        reply_markup=valuation_profitability_keyboard(),
    )
    await callback.answer()


@router.callback_query(ValuationFlow.express_share, F.data == "valuation:low_share:not_now")
async def valuation_low_share_not_now(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await return_to_base_state(
        callback.message,
        state,
        "Понял! Если что-то изменится — мы всегда здесь. "
        "Вы по-прежнему будете получать новости и обновления продуктов. "
        "Удачи в развитии бизнеса! 🤝",
    )
    await callback.answer()


@router.callback_query(ValuationFlow.express_profitability, F.data.startswith("valuation:profit:"))
async def valuation_express_profitability(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    option = callback.data.removeprefix("valuation:profit:")
    profitability = VALUATION_PROFITABILITY_MAP.get(option)
    if profitability is None:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    data = await state.get_data()
    revenue_mln = float(data["valuation_revenue_mln"])
    profit_mln = revenue_mln * (profitability / 100)
    valuation_mln = round(profit_mln * VALUATION_MULTIPLE, 1)
    profit_mln_rounded = round(profit_mln, 1)

    await state.update_data(
        valuation_profitability_percent=profitability,
        valuation_profit_mln=profit_mln_rounded,
        valuation_result_mln=valuation_mln,
    )
    await save_funnel_fields(
        user_id,
        valuation_profitability_percent=profitability,
        valuation_profit_mln=profit_mln_rounded,
        valuation_result_mln=valuation_mln,
    )

    await add_event(
        user_id,
        "valuation_express_completed",
        (
            f"revenue_mln={revenue_mln};share={data.get('valuation_share_percent')};"
            f"profitability={profitability};profit_mln={profit_mln_rounded};valuation_mln={valuation_mln}"
        ),
    )

    await state.set_state(ValuationFlow.express_continue)
    loading_message = await callback.message.answer("⏳ Оцениваем вашу фирму...")
    await delete_message_safe(loading_message)
    await callback.message.answer(
        "Оценка стоимости вашей фирмы\n"
        f"{profit_mln_rounded:.1f} × {VALUATION_MULTIPLE:.1f} = {valuation_mln:.1f} млн руб.\n"
        "— стандарт для бухгалтерских практик\n\n"
        "Есть несколько важных нюансов, которые нужно уточнить. "
        "Вы согласны ответить на ещё несколько вопросов, чтобы быть точнее и учесть важные моменты?",
        reply_markup=valuation_continue_keyboard(),
    )
    await callback.answer()


@router.callback_query(ValuationFlow.express_continue, F.data == "valuation:continue:yes")
async def valuation_continue_yes(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await state.set_state(ValuationFlow.precise_clients_total)
    await callback.message.answer(
        "Отлично! Теперь несколько вопросов о вашем клиентском портфеле и команде. "
        "Это поможет нам понять, как ИИ-автоматизация и инвестиции лучше всего впишутся именно в вашу фирму.\n\n"
        "Ещё 5 вопросов — займёт пару минут 👇\n\n"
        "<b>Q4: Сколько у вас активных клиентов?</b>\n\n"
        "Считайте только тех, кто получает услуги по базовой бухгалтерии. "
        "Напишите одно число (например: 50, 250, 500).",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(ValuationFlow.express_continue, F.data == "valuation:continue:no")
async def valuation_continue_no(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await return_to_base_state(
        callback.message,
        state,
        "Спасибо, что нашли время пройти нашу экспресс-оценку компании 🙌\n"
        "Каждый день мы делимся в этом чате материалами о нашей работе и достижениях 📚✨. "
        "Если вы хотите назначить звонок, чтобы обсудить возможную сделку, "
        "нажмите «Забронировать встречу» в меню 📅. "
        "В противном случае будем рады встретиться с вами на одном из наших ближайших мероприятий "
        "— список доступен в меню 🤝.",
    )
    await callback.answer()


@router.message(ValuationFlow.precise_clients_total, F.text)
async def valuation_precise_q4_clients_total(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    cancel_valuation_idle_task(user_id)
    value = parse_positive_int(message.text.strip())
    if value is None:
        await message.answer("Пожалуйста, введите число активных клиентов. Например: 250")
        return

    await state.update_data(valuation_c1=value)
    await save_funnel_fields(user_id, valuation_c1=value)
    await state.set_state(ValuationFlow.precise_clients_key)
    await message.answer(
        "<b>Q5: Сколько клиентов приносят основную часть вашей выручки от базовой бухгалтерии?</b>\n\n"
        "Подсказка: обычно 10–20% клиентов дают 80% дохода.\n"
        "Напишите одно число (например: 5, 15, 40).",
        parse_mode="HTML",
    )


@router.message(ValuationFlow.precise_clients_key, F.text)
async def valuation_precise_q5_key_clients(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    cancel_valuation_idle_task(user_id)
    key_clients = parse_positive_int(message.text.strip())
    if key_clients is None:
        await message.answer("Пожалуйста, введите число ключевых клиентов. Например: 15")
        return

    data = await state.get_data()
    total_clients = int(data["valuation_c1"])
    if key_clients > total_clients:
        await message.answer(
            "Количество ключевых клиентов не может быть больше общего числа активных клиентов. "
            "Проверьте значение и введите ещё раз."
        )
        return

    await state.update_data(valuation_c2=key_clients)
    await save_funnel_fields(user_id, valuation_c2=key_clients)
    await state.set_state(ValuationFlow.precise_top5_share)
    await message.answer(
        "<b>Q6: Какую долю выручки от базовой бухгалтерии приносят ваши 5 крупнейших клиентов?</b>",
        parse_mode="HTML",
        reply_markup=valuation_q6_share_keyboard(),
    )


@router.callback_query(ValuationFlow.precise_top5_share, F.data.startswith("valuation:q6:"))
async def valuation_precise_q6_top5_share(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    option = callback.data.removeprefix("valuation:q6:")
    if option not in VALUATION_Q6_RF2_MAP:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    await state.update_data(valuation_c3=option)
    await save_funnel_fields(user_id, valuation_c3=option)
    await state.set_state(ValuationFlow.precise_headcount)
    await callback.message.answer(
        "<b>Q7: Сколько бухгалтеров занято на базовых операциях?</b>\n\n"
        "Первичка, сверки, банк-клиент — не считая руководителей направлений и аудиторов.\n"
        "Напишите одно число (например: 5, 15, 40).",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ValuationFlow.precise_headcount, F.text)
async def valuation_precise_q7_headcount(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    cancel_valuation_idle_task(user_id)
    headcount = parse_positive_int(message.text.strip())
    if headcount is None:
        await message.answer("Пожалуйста, введите число сотрудников. Например: 15")
        return

    await state.update_data(valuation_h=headcount)
    await save_funnel_fields(user_id, valuation_h=headcount)
    await state.set_state(ValuationFlow.precise_automation_level)
    await message.answer(
        "<b>Q8: Используете ли вы инструменты автоматизации в бухгалтерии?</b>\n\n"
        "Выберите вариант ответа:",
        parse_mode="HTML",
        reply_markup=valuation_q8_automation_level_keyboard(),
    )


@router.callback_query(ValuationFlow.precise_automation_level, F.data.startswith("valuation:q8:"))
async def valuation_precise_q8_automation_level(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    option = callback.data.removeprefix("valuation:q8:")
    if option not in {"none", "partial", "advanced"}:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    await state.update_data(valuation_q8_level=option)
    await save_funnel_fields(user_id, valuation_q8_level=option)
    if option != "advanced":
        await valuation_send_precise_result(callback, state)
        await callback.answer()
        return

    await state.set_state(ValuationFlow.precise_automation_tools)
    await state.update_data(valuation_auto_tools=[])
    await callback.message.answer(
        "Серьёзный уровень! Какие решения используете?\n"
        "Отметьте всё, что подходит — мы учтём это при планировании перехода на платформу AIVEL.",
        reply_markup=valuation_automation_tools_keyboard(set()),
    )
    await callback.answer()


@router.callback_query(ValuationFlow.precise_automation_tools, F.data.startswith("valuation:auto:toggle:"))
async def valuation_q8_auto_toggle(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    option = callback.data.removeprefix("valuation:auto:toggle:")
    allowed = {"rpa", "bots", "ocr", "ai", "bi"}
    if option not in allowed:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    data = await state.get_data()
    selected = set(data.get("valuation_auto_tools", []))
    if option in selected:
        selected.remove(option)
    else:
        selected.add(option)

    await state.update_data(valuation_auto_tools=sorted(selected))
    await save_funnel_fields(user_id, valuation_auto_tools="|".join(sorted(selected)))
    await callback.message.edit_reply_markup(reply_markup=valuation_automation_tools_keyboard(selected))
    await callback.answer()


@router.callback_query(ValuationFlow.precise_automation_tools, F.data == "valuation:auto:other:hint")
async def valuation_q8_auto_other_hint(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await callback.answer()
    await callback.message.answer("Напишите в чат, какие ещё решения используете. Затем нажмите «✅ Готово».")


@router.message(ValuationFlow.precise_automation_tools, F.text)
async def valuation_q8_auto_other_text(message: Message, state: FSMContext):
    user_id = await get_db_user_id(message)
    cancel_valuation_idle_task(user_id)
    raw = message.text.strip()
    if not raw:
        await message.answer("Опишите решение текстом или нажмите «✅ Готово».")
        return

    data = await state.get_data()
    custom = data.get("valuation_auto_other", [])
    custom.append(raw)
    await state.update_data(valuation_auto_other=custom)
    await save_funnel_fields(user_id, valuation_auto_other="\n".join(custom))
    await message.answer("Добавили. Если нужно, отправьте ещё вариант или нажмите «✅ Готово».")


@router.callback_query(ValuationFlow.precise_automation_tools, F.data == "valuation:auto:done")
async def valuation_q8_auto_done(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await valuation_send_precise_result(callback, state)
    await callback.answer()


async def valuation_send_precise_result(target: Message | CallbackQuery, state: FSMContext):
    message = target.message if isinstance(target, CallbackQuery) else target
    data = await state.get_data()
    c1 = int(data["valuation_c1"])
    c2 = int(data["valuation_c2"])
    c3 = str(data["valuation_c3"])
    express_valuation = float(data.get("valuation_result_mln", 0.0))

    rf1 = valuation_rf1_score(c1, c2)
    rf2 = VALUATION_Q6_RF2_MAP[c3]
    rf3 = valuation_rf3_score(c1)
    rf_comp = round((rf1 * 0.4) + (rf2 * 0.4) + (rf3 * 0.2), 2)
    new_valuation = round(express_valuation * rf_comp, 1)

    if rf_comp >= 1.00:
        emoji, comment = "🟢", (
            "Ваш клиентский портфель хорошо диверсифицирован — это повышает устойчивость бизнеса и его оценку."
        )
    elif 0.90 <= rf_comp <= 0.99:
        emoji, comment = "🟡", (
            "Портфель имеет умеренную концентрацию. После вступления в сеть мы поможем расширить клиентскую базу через маркетинг и M&A."
        )
    elif 0.80 <= rf_comp <= 0.89:
        emoji, comment = "🟠", (
            "Есть зависимость от крупных клиентов. Одна из первых задач после партнёрства — диверсификация через привлечение новых клиентов и небольшие приобретения."
        )
    else:
        emoji, comment = "🔴", (
            "Высокая зависимость от нескольких клиентов — это главный риск. Мы обсудим план диверсификации на звонке с менеджером."
        )

    user_id = await get_db_user_id(target)
    await add_event(
        user_id,
        "valuation_precise_completed",
        (
            f"c1={c1};c2={c2};c3={c3};rf1={rf1:.2f};rf2={rf2:.2f};rf3={rf3:.2f};"
            f"rfcomp={rf_comp:.2f};express={express_valuation:.1f};new={new_valuation:.1f}"
        ),
    )

    await state.update_data(valuation_rfcomp=rf_comp, valuation_new_result_mln=new_valuation)
    await save_funnel_fields(user_id, valuation_rfcomp=rf_comp, valuation_new_result_mln=new_valuation)
    await state.set_state(ValuationFlow.precise_post_result)
    loading_message = await message.answer("⏳ Оцениваем вашу фирму...")
    await delete_message_safe(loading_message)
    await message.answer(
        "Новая оценка вашей фирмы: "
        f"<b>{format_mln(new_valuation)} млн руб.</b>\n\n"
        "Результаты анализа клиентского портфеля, на основе ваших ответов мы оценили устойчивость клиентской базы:\n"
        f"{emoji} <b>RFcomp: {rf_comp:.2f}</b>\n"
        f"{comment}",
        parse_mode="HTML",
    )
    await message.answer(VALUATION_EXCEL_TEXT, reply_markup=valuation_excel_offer_keyboard())
    await schedule_valuation_idle_followup(message, state, user_id)


@router.callback_query(F.data == "valuation:excel:download")
async def valuation_post_excel_download(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await send_excel_and_wait_for_user(callback, state)


@router.callback_query(ValuationFlow.precise_post_result, F.data == "valuation:idle:models")
async def valuation_idle_models(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    data = await state.get_data()
    profit_mln = float(data.get("valuation_profit_mln", 8.0))
    valuation_mln = round(profit_mln * VALUATION_MULTIPLE, 1)
    investor_25_mln = round(valuation_mln * 0.25, 1)

    await callback.message.answer_photo(
        photo=VALUATION_MODELS_IMAGE_URL,
        caption=(
            "<b>🚀 Модели</b>\n"
            "Мы предлагаем 4 сценария — от «ничего не делать» до «построить группу компаний». "
            "Каждый влияет на вашу прибыль по-разному.\n\n"
            f"Сценарий компании с прибылью {format_mln(profit_mln)} млн ₽\n"
            f"Оценка компании: {format_mln(profit_mln)} × {VALUATION_MULTIPLE:.1f} = {format_mln(valuation_mln)} млн ₽\n"
            f"Стоимость 25% для инвестора: {format_mln(investor_25_mln)} млн ₽"
        ),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(ValuationFlow.precise_post_result, F.data == "valuation:idle:faq")
async def valuation_idle_faq(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await send_valuation_faq_topics(callback.message)
    await callback.answer()


@router.callback_query(F.data == "valuation:faq:topics")
async def valuation_faq_topics(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    await send_valuation_faq_topics(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith("valuation:faq:topic:"))
async def valuation_faq_topic_selected(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    topic = callback.data.removeprefix("valuation:faq:topic:")
    mapping = {
        "price": (
            "Оценка и цена",
            [
                ("price_calc", "Как оценивается моя фирма?"),
                ("price_debt", "А если у меня долги?"),
                ("price_25", "Сколько я получу за 25%?"),
                ("price_cash", "Cash-In vs Cash-Out — что выгоднее?"),
            ],
        ),
        "roles": (
            "Кто за что отвечает",
            [
                ("roles_mgmt", "Что изменится в управлении?"),
                ("roles_fire", "Могут ли меня уволить?"),
            ],
        ),
        "process": (
            "Как проходит сделка",
            [
                ("process_steps", "Шаги от знакомства до сделки"),
                ("process_fast", "А можно быстрее?"),
            ],
        ),
        "ai": (
            "Внедрение ИИ",
            [
                ("ai_speed", "Как быстро заработает ИИ?"),
                ("ai_cost", "Сколько стоит внедрение?"),
                ("ai_scope", "Что автоматизируется?"),
            ],
        ),
        "changes": (
            "Что меняется в фирме",
            [
                ("changes_clients", "Что изменится для моих клиентов?"),
                ("changes_team", "А что с моей командой?"),
            ],
        ),
        "legal": (
            "Юридические вопросы",
            [
                ("legal_structure", "Как юридически оформлена сделка?"),
                ("legal_exit", "А если я захочу выйти?"),
            ],
        ),
    }
    selected = mapping.get(topic)
    if selected is None:
        await callback.answer("Неизвестная тема", show_alert=True)
        return

    title, questions = selected
    questions_text = "\n".join([f"{idx}. {label}" for idx, (_, label) in enumerate(questions, start=1)])
    await callback.message.answer(
        f"Раздел: <b>{title}</b>\n\nВопросы:\n{questions_text}\n\nВыберите номер вопроса:",
        parse_mode="HTML",
        reply_markup=valuation_faq_question_numbers_keyboard(topic, len(questions)),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^valuation:faq:[a-z_]+:q[0-9]+$"))
async def valuation_faq_question_selected(callback: CallbackQuery):
    user_id = await get_db_user_id(callback)
    cancel_valuation_idle_task(user_id)
    _, _, topic, qnum_raw = callback.data.split(":")
    qnum = int(qnum_raw.removeprefix("q"))
    topic_question_map = {
        "price": ["price_calc", "price_debt", "price_25", "price_cash"],
        "roles": ["roles_mgmt", "roles_fire"],
        "process": ["process_steps", "process_fast"],
        "ai": ["ai_speed", "ai_cost", "ai_scope"],
        "changes": ["changes_clients", "changes_team"],
        "legal": ["legal_structure", "legal_exit"],
    }
    question_keys = topic_question_map.get(topic, [])
    if qnum <= 0 or qnum > len(question_keys):
        await callback.answer("Неизвестный вопрос", show_alert=True)
        return
    question_id = question_keys[qnum - 1]
    answers = valuation_faq_answers()
    text = answers.get(question_id)
    if text is None:
        await callback.answer("Ответ пока не найден", show_alert=True)
        return

    if question_id == "roles_mgmt":
        await callback.message.answer(f"Матрица ролей: {VALUATION_ROLES_IMAGE_URL}", disable_web_page_preview=False)

    await callback.message.answer(text, parse_mode="HTML")
    await callback.message.answer("Вы можете выбрать другой вопрос или вернуться к темам.", reply_markup=valuation_faq_topics_keyboard())
    await callback.answer()


@router.message(SimulateFlow.express_accountants, F.text)
async def simulate_express_accountants(message: Message, state: FSMContext):
    accountants = parse_positive_int(message.text.strip())
    if accountants is None:
        await message.answer("Введите количество бухгалтеров целым числом. Пример: 15")
        return

    await state.update_data(express_accountants=accountants)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), accountants_count=accountants)
    await state.set_state(SimulateFlow.express_salary)
    await message.answer(
        "2️⃣ Средняя зарплата бухгалтера (₽/мес, включая налоги)?\n\n"
        "Напишите свой ответ сообщением.\n"
        f"Например: {DEFAULT_EXPRESS_SALARY}",
        parse_mode="HTML",
        
    )


@router.callback_query(F.data == "simulate:cancel")
async def simulate_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await return_to_base_state(callback.message, state, "Ок, вернули вас в главное меню.")
    await callback.answer()


@router.message(SimulateFlow.express_salary, F.text)
async def simulate_express_salary(message: Message, state: FSMContext):
    salary = parse_positive_int(message.text.strip())
    if salary is None:
        await message.answer("Введите среднюю зарплату бухгалтера числом в ₽. Пример: 80000")
        return

    await state.update_data(express_salary=salary)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), avg_salary=salary)
    await send_express_result(message, state)


@router.message(SimulateFlow.precise_clients, F.text & (F.text.casefold() != "пропустить"))
async def simulate_precise_clients(message: Message, state: FSMContext):
    clients = parse_positive_int(message.text.strip())
    if clients is None:
        await message.answer("Введите количество активных клиентов целым числом. Пример: 120")
        return

    await state.update_data(precise_clients=clients)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), active_clients_count=clients)
    await state.set_state(SimulateFlow.precise_contacts)
    await message.answer(
        "Поделитесь с нами вашими контактными данными (Ваше имя, Email, Телефон, Компания, Вебсайт)\n",
        parse_mode="HTML",
        reply_markup=simulate_contacts_choice_keyboard(),
    )


@router.message(SimulateFlow.precise_margin, F.text & (F.text.casefold() != "пропустить"))
async def simulate_precise_margin(message: Message, state: FSMContext):
    margin = parse_positive_int(message.text.strip())
    if margin is None or margin > 100:
        await message.answer("Введите валовую маржу числом от 1 до 100. Пример: 35")
        return

    await state.update_data(precise_margin=margin)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), margin_percent=margin)
    await finalize_precise_assessment(message, state)


@router.callback_query(F.data.in_({"simulate:precise:more", "simulate:precise:more5"}))
async def simulate_precise_more(callback: CallbackQuery, state: FSMContext):
    if await reject_inactive_tool_callback(callback, state):
        return

    if not await ensure_simulate_consent(callback, state):
        return

    data = await state.get_data()
    await state.update_data(
        precise_accountants=int(data.get("express_accountants", DEFAULT_EXPRESS_ACCOUNTANTS)),
        precise_salary=int(data.get("express_salary", DEFAULT_EXPRESS_SALARY)),
    )
    await state.set_state(SimulateFlow.precise_advisory)
    await callback.message.answer(
        "✅ <b>Точная оценка</b>\n\n"
        "3️⃣ Какой % клиентов требует нестандартных консультаций / advisory работы?\n"
        "Сложные налоговые кейсы, реструктуризация, M&A-поддержка, специальные отраслевые требования\n\n"
        "Выберите вариант ответа:\n"
        "• Менее 10% — почти все клиенты стандартные\n"
        "• 10-20% — есть несколько сложных клиентов\n"
        "• >20% — заметная доля advisory\n",
        parse_mode="HTML",
        reply_markup=simulate_plus3_advisory_keyboard(),
    )
    await callback.answer()


@router.callback_query(SimulateFlow.precise_standardization, F.data.startswith("simulate:plus3:std:"))
async def simulate_plus3_standardization(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[-1]
    if value != "skip" and value not in STANDARDIZATION_LABELS:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    normalized = "medium" if value == "skip" else value
    await state.update_data(plus3_standardization=normalized)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), standardization_level=normalized)
    await state.set_state(SimulateFlow.precise_automation)
    await callback.message.answer(
        "6️⃣ Используете ли вы сейчас какие-то инструменты автоматизации?\n\n",
        parse_mode="HTML",
        reply_markup=simulate_plus3_automation_keyboard(),
    )
    await callback.answer()


@router.callback_query(SimulateFlow.precise_automation, F.data.startswith("simulate:plus3:auto:"))
async def simulate_plus3_automation(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[-1]
    if value != "skip" and value not in AUTOMATION_LABELS:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    normalized = "partial" if value == "skip" else value
    await state.update_data(plus3_automation=normalized)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), automation_level=normalized)
    await state.set_state(SimulateFlow.precise_margin)
    await callback.message.answer(
        "7️⃣ Текущая валовая маржа (%)?\n\n"
        "Напишите свой ответ сообщением.\n"
        "Например: 35",
        parse_mode="HTML",
        
    )
    await callback.answer()


@router.callback_query(SimulateFlow.precise_advisory, F.data.startswith("simulate:plus3:advisory:"))
async def simulate_plus3_advisory(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[-1]
    if value != "skip" and value not in ADVISORY_LABELS:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    normalized = "10_20" if value == "skip" else value
    await state.update_data(plus3_advisory=normalized)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), advisory_band=normalized)
    await state.set_state(SimulateFlow.precise_clients)
    await callback.message.answer(
        "4️⃣ Количество активных клиентов?\n\n"
        "Напишите свой ответ сообщением.\n"
        "Например: 120",
        parse_mode="HTML",
        
    )
    await callback.answer()


@router.message(SimulateFlow.precise_clients, F.text.casefold() == "пропустить")
async def simulate_precise_clients_skip_text(message: Message, state: FSMContext):
    await state.update_data(precise_clients=0)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), active_clients_count=0)
    await state.set_state(SimulateFlow.precise_contacts)
    await message.answer(
        "Поделитесь с нами вашими контактными данными (Ваше имя, Email, Телефон, Компания, Вебсайт)\n",
        parse_mode="HTML",
        reply_markup=simulate_contacts_choice_keyboard(),
    )


@router.callback_query(SimulateFlow.precise_contacts, F.data == "simulate:contacts:share")
async def simulate_contacts_share(callback: CallbackQuery, state: FSMContext):
    await delete_message_safe(callback.message)
    await state.set_state(SimulateFlow.precise_contact_name)
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    await callback.message.answer(
        "Введите ваше имя:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(SimulateFlow.precise_contact_name, F.text)
async def simulate_contact_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(contact_name=name)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_name=name)
    await state.set_state(SimulateFlow.precise_contact_email)
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    await message.answer(
        "Введите ваш Email:",
        reply_markup=None,
    )


@router.callback_query(SimulateFlow.precise_contact_name, F.data == "simulate:contacts:name:skip")
async def simulate_contact_name_skip(callback: CallbackQuery, state: FSMContext):
    if (await state.get_data()).get("force_full_contacts", False):
        await callback.answer("Этот шаг нельзя пропустить.", show_alert=True)
        return

    await state.update_data(contact_name="")
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_name="")
    await state.set_state(SimulateFlow.precise_contact_email)
    await callback.message.answer(
        "Введите ваш Email:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(SimulateFlow.precise_contact_email, F.text)
async def simulate_contact_email(message: Message, state: FSMContext):
    email = message.text.strip()
    await state.update_data(contact_email=email)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_email=email)
    await state.set_state(SimulateFlow.precise_contact_phone)
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    await message.answer(
        "Введите ваш телефон:",
        reply_markup=None,
    )


@router.callback_query(SimulateFlow.precise_contact_email, F.data == "simulate:contacts:email:skip")
async def simulate_contact_email_skip(callback: CallbackQuery, state: FSMContext):
    if (await state.get_data()).get("force_full_contacts", False):
        await callback.answer("Этот шаг нельзя пропустить.", show_alert=True)
        return

    await state.update_data(contact_email="")
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_email="")
    await state.set_state(SimulateFlow.precise_contact_phone)
    await callback.message.answer(
        "Введите ваш телефон:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(SimulateFlow.precise_contact_phone, F.text)
async def simulate_contact_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(contact_phone=phone)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_phone=phone)
    await state.set_state(SimulateFlow.precise_contact_company)
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    await message.answer(
        "Введите название вашей компании:",
        reply_markup=None,
    )


@router.callback_query(SimulateFlow.precise_contact_phone, F.data == "simulate:contacts:phone:skip")
async def simulate_contact_phone_skip(callback: CallbackQuery, state: FSMContext):
    if (await state.get_data()).get("force_full_contacts", False):
        await callback.answer("Этот шаг нельзя пропустить.", show_alert=True)
        return

    await state.update_data(contact_phone="")
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), contact_phone="")
    await state.set_state(SimulateFlow.precise_contact_company)
    await callback.message.answer(
        "Введите название вашей компании:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(SimulateFlow.precise_contact_company, F.text)
async def simulate_contact_company(message: Message, state: FSMContext):
    company = message.text.strip()
    await state.update_data(contact_company=company)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_profile_field(int(user_id), "company", company)
    await state.set_state(SimulateFlow.precise_contact_website)
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    await message.answer(
        "Введите сайт вашей компании:",
        reply_markup=website_optional_keyboard() if force_full_contacts else None,
    )


@router.callback_query(SimulateFlow.precise_contact_company, F.data == "simulate:contacts:company:skip")
async def simulate_contact_company_skip(callback: CallbackQuery, state: FSMContext):
    if (await state.get_data()).get("force_full_contacts", False):
        await callback.answer("Этот шаг нельзя пропустить.", show_alert=True)
        return

    await state.update_data(contact_company="")
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_profile_field(int(user_id), "company", "")
    await state.set_state(SimulateFlow.precise_contact_website)
    await callback.message.answer(
        "Введите сайт вашей компании:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(SimulateFlow.precise_contact_website, F.text)
async def simulate_contact_website(message: Message, state: FSMContext):
    website_raw = message.text.strip()
    if not URL_RE.match(website_raw):
        await message.answer("Ссылка выглядит некорректно. Пример: www.company.com или https://company.com")
        return

    await state.update_data(contact_website=website_raw)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_profile_field(int(user_id), "company_website", website_raw)

    data = await state.get_data()
    await state.update_data(
        precise_contacts=(
            f"name={data.get('contact_name', '')}|email={data.get('contact_email', '')}|"
            f"phone={data.get('contact_phone', '')}|company={data.get('contact_company', '')}|"
            f"website={website_raw}"
        ),
    )
    force_full_contacts = bool((await state.get_data()).get("force_full_contacts", False))
    if force_full_contacts:
        await return_to_base_state(message, state, THANKS_DEEP_TEXT)
        return

    await state.set_state(SimulateFlow.precise_standardization)
    await ask_precise_standardization_question(message)


@router.callback_query(SimulateFlow.precise_contact_website, F.data == "onboarding:no_site")
async def simulate_contact_website_no_site(callback: CallbackQuery, state: FSMContext):
    await state.update_data(contact_website=NO_SITE_MARKER)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_profile_field(int(user_id), "company_website", NO_SITE_MARKER)

    data = await state.get_data()
    await state.update_data(
        precise_contacts=(
            f"name={data.get('contact_name', '')}|email={data.get('contact_email', '')}|"
            f"phone={data.get('contact_phone', '')}|company={data.get('contact_company', '')}|"
            f"website={NO_SITE_MARKER}"
        ),
    )
    if (await state.get_data()).get("force_full_contacts", False):
        await return_to_base_state(callback.message, state, THANKS_DEEP_TEXT)
        await callback.answer()
        return

    await state.set_state(SimulateFlow.precise_standardization)
    await ask_precise_standardization_question(callback.message)
    await callback.answer()


@router.message(SimulateFlow.precise_margin, F.text.casefold() == "пропустить")
async def simulate_precise_margin_skip(message: Message, state: FSMContext):
    await state.update_data(precise_margin=0)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), margin_percent=0)
    await finalize_precise_assessment(message, state)


async def finalize_precise_assessment(target: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    express_result = calculate_express_operation_savings(
        int(data["precise_accountants"]),
        int(data["precise_salary"]),
    )
    precise_result = calculate_precise_savings_from_express(
        express_result=express_result,
        standardization_band=str(data.get("plus3_standardization", "medium")),
        automation_band=str(data.get("plus3_automation", "partial")),
        advisory_band=str(data.get("plus3_advisory", "10_20")),
    )

    k = precise_result["k"]
    released_6 = int(round(express_result["released_6"] * k))
    released_12 = int(round(express_result["released_12"] * k))
    payroll_saved_6 = express_result["payroll_saved_6"] * k
    payroll_saved_12 = express_result["payroll_saved_12"] * k
    ai_cost_6 = express_result["ai_cost_6"] * k
    ai_cost_12 = express_result["ai_cost_12"] * k
    net_6 = express_result["net_6"] * k
    net_12 = express_result["net_12"] * k

    precise_range = f"{format_rub(min(net_6, net_12))} – {format_rub(max(net_6, net_12))} ₽/мес"
    text = (
        "🎯 <b>Ваши результаты с Aivel:</b>\n\n"
        "Спасибо — на основе ваших ответов мы уточнили базовую оценку и рассчитали более точный потенциал "
        "экономии с учётом специфики именно вашей фирмы.\n"
        "Шаги расчёта через 6 месяцев и через 12 месяцев\n\n"
        "1. <b>Число высвобождаемых бухгалтеров</b>\n"
        f"• через 6 месяцев: <b>{released_6}</b>\n"
        f"• через 12 месяцев: <b>{released_12}</b>\n\n"
        "2. <b>Сохраняемая месячная зарплатная масса</b>\n"
        f"• через 6 месяцев: <b>{format_rub(payroll_saved_6)} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(payroll_saved_12)} ₽ в месяц</b>\n\n"
        "3. <b>Новая стоимость операций на базе искусственного интеллекта</b>\n"
        f"• через 6 месяцев: <b>{format_rub(ai_cost_6)} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(ai_cost_12)} ₽ в месяц</b>\n\n"
        "4. <b>Чистая экономия в месяц</b>\n"
        f"• через 6 месяцев: <b>{format_rub(net_6)} ₽ в месяц</b>\n"
        f"• через 12 месяцев: <b>{format_rub(net_12)} ₽ в месяц</b>\n\n"
        f"<i>Итоговый K: {k:.2f}</i>\n"
        f"<i>Диапазон точной экономии: {precise_range}</i>"
    )

    user_id = await get_db_user_id(target)
    await save_funnel_fields(
        user_id,
        precise_assessment=precise_range,
        express_saving_6=int(round(net_6)),
        express_saving_12=int(round(net_12)),
    )
    await add_event(
        user_id,
        "simulate_precise_completed",
        (
            f"accountants={data.get('precise_accountants', 0)};salary={data.get('precise_salary', 0)};"
            f"clients={data.get('precise_clients', 0)};contacts={data.get('precise_contacts', '')};"
            f"margin={data.get('precise_margin', 0)};std={data.get('plus3_standardization', 'medium')};"
            f"auto={data.get('plus3_automation', 'partial')};advisory={data.get('plus3_advisory', '10_20')};"
            f"k={k:.4f};range={precise_range};net6={format_rub(net_6)};net12={format_rub(net_12)}"
        ),
    )

    await state.set_state(SimulateFlow.precise_growth)
    if isinstance(target, CallbackQuery):
        await target.message.answer(text, parse_mode="HTML")
        await target.message.answer(
            "Планируете ли вы рост в ближайшие 12-24 месяца?",
            reply_markup=simulate_growth_keyboard(),
        )
    else:
        await target.answer(text, parse_mode="HTML")
        await target.answer(
            "Планируете ли вы рост в ближайшие 12-24 месяца?",
            reply_markup=simulate_growth_keyboard(),
        )


@router.callback_query(SimulateFlow.precise_growth, F.data.startswith("simulate:post:growth:"))
async def simulate_post_growth(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[-1]
    if value not in {"none", "normal", "fast"}:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    await state.update_data(post_growth=value)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), growth_band=value)
    await state.set_state(SimulateFlow.precise_mna)
    await callback.message.answer(
        "Рассматриваете ли вы M&A / привлечение инвестиций?",
        reply_markup=simulate_mna_keyboard(),
    )
    await callback.answer()


@router.callback_query(SimulateFlow.precise_mna, F.data.startswith("simulate:post:mna:"))
async def simulate_post_mna(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[-1]
    if value not in {"yes", "no"}:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    await state.update_data(post_mna=value)
    user_id = (await state.get_data()).get("db_user_id")
    if user_id:
        await save_funnel_fields(int(user_id), mna_interest=value)
    await state.set_state(SimulateFlow.precise_wait_excel)
    await callback.message.answer(
        "🎯 Серьёзно рассматриваете внедрение? Загрузите Excel — получите полный бизнес-кейс от нашей команды.",
        reply_markup=simulate_deep_assessment_keyboard(),
    )
    await callback.answer()


@router.callback_query(SimulateFlow.precise_wait_excel, F.data == "simulate:deep:download")
async def simulate_deep_download(callback: CallbackQuery, state: FSMContext):
    await send_excel_and_wait_for_user(callback, state)


@router.callback_query(SimulateFlow.precise_wait_excel, F.data == "simulate:deep:sent_email")
async def simulate_deep_sent_email(callback: CallbackQuery, state: FSMContext):
    user_id = await get_db_user_id(callback)
    await save_funnel_fields(user_id, uploaded_file_link="отправил на почту")
    await add_event(user_id, "simulate_deep_sent_email")
    await return_to_base_state(callback.message, state, THANKS_DEEP_TEXT)
    await callback.answer()


@router.callback_query(SimulateFlow.precise_wait_excel, F.data == "simulate:deep:back")
async def simulate_deep_back(callback: CallbackQuery, state: FSMContext):
    await return_to_base_state(callback.message, state, THANKS_TOOL_TEXT)
    await callback.answer()


@router.callback_query(SimulateFlow.precise_wait_excel, F.data == "simulate:deep:back_wait")
async def simulate_deep_back_wait(callback: CallbackQuery, state: FSMContext):
    await return_to_base_state(callback.message, state, THANKS_TOOL_TEXT)
    await callback.answer()


@router.message(SimulateFlow.precise_wait_excel, F.document)
async def simulate_wait_excel_upload(message: Message, state: FSMContext):
    document = message.document
    if not is_excel_filename(document.file_name):
        await message.answer("Похоже, это не Excel-файл. Пожалуйста, отправьте файл в формате .xlsx/.xls/.xlsm.")
        return

    user_id = await get_db_user_id(message)
    uploaded_file_link = f"telegram_file_id:{document.file_id}"
    try:
        telegram_file = await message.bot.get_file(document.file_id)
        if telegram_file.file_path:
            safe_file_path = quote(telegram_file.file_path, safe="/")
            uploaded_file_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{safe_file_path}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to build downloadable link for file_id=%s: %s", document.file_id, exc)

    await save_funnel_fields(
        user_id,
        file_downloaded=True,
        uploaded_file_link=uploaded_file_link,
    )
    await add_event(user_id, "simulate_deep_excel_uploaded", document.file_name)

    personal_data = await get_user_personal_data(user_id)
    if not is_personal_data_complete(personal_data):
        await state.clear()
        await state.update_data(db_user_id=user_id, force_full_contacts=True)
        await state.set_state(SimulateFlow.precise_contact_name)
        await message.answer(MISSING_PERSONAL_DATA_TEXT)
        await message.answer("Введите ваше имя:")
        return

    await return_to_base_state(message, state, THANKS_DEEP_TEXT)


@router.message(SimulateFlow.precise_wait_excel)
async def simulate_wait_excel_invalid(message: Message):
    await message.answer(
        "Пожалуйста, отправьте Excel-файл (.xlsx/.xls/.xlsm) или используйте кнопки ниже.",
        reply_markup=simulate_deep_wait_keyboard(),
    )


@router.message()
async def unexpected_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    user_id = await get_db_user_id(message)
    await add_event(
        user_id,
        "unexpected_message",
        f"state={current_state};has_text={bool(message.text)};has_document={bool(message.document)}",
    )

    if current_state:
        await message.answer(
            "Простите, сейчас я жду ответ на текущий вопрос или нажатие кнопки. "
            "Если хотите выйти из сценария, нажмите «🏠 В меню» или «❌ Отменить».",
        )
        return

    await message.answer(
        "Простите, не знаю, что с этим делать. Выберите раздел в меню ниже 👇",
        reply_markup=persistent_main_keyboard(),
    )


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, state: FSMContext):
    await answer_stale_callback(callback, state)
