# Sales Tunnel Bot MVP

Telegram-бот для онбординга пользователей Aivel, расчёта экономии, оценки сделки и записи на встречу.

## Функционал

- `/start` — приветствие, сохранение пользователя и показ основного меню.
- Основное меню:
  - записаться на встречу;
  - посмотреть мероприятия из Google Sheets;
  - открыть FAQ о сделке;
  - перейти к продуктовым сценариям.
- Калькулятор экономии:
  - экспресс-оценка по числу бухгалтеров и средней зарплате;
  - уточнённая оценка с дополнительными вопросами;
  - скачивание Excel-файла для самостоятельной оценки.
- Сценарий «Сделка и рост»:
  - ввод финансовых показателей;
  - расчёт ориентировочной оценки;
  - FAQ и follow-up-сообщения.
- Запись на встречу через Calendly и встроенный календарь.
- Прогревочные push-сообщения из Google Sheets.
- Экспорт пользователей и funnel-полей в Google Sheets.

## Структура проекта

```text
Sales-Tunnel-for-Targets/
├── main.py
├── requirements.txt
├── scripts/
│   ├── check_callback_coverage.py
│   └── check_get_db_user_id_target_usage.py
└── app/
    ├── __init__.py
    ├── assets/
    │   └── aivel_pro_assessment.xlsx
    ├── calendly.py
    ├── config.py
    ├── db.py
    ├── events.py
    ├── export_sync.py
    ├── handlers/
    │   ├── __init__.py
    │   └── start.py
    ├── keyboards.py
    ├── scoring.py
    ├── states.py
    └── warmup.py
```

## Установка

1. Клонировать репозиторий:

```bash
git clone <URL>
cd Sales-Tunnel-for-Targets
```

2. Создать виртуальное окружение и активировать:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Установить зависимости:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Если при установке видите ошибки вида `ProxyError ... 403 Forbidden` и `No matching distribution found`, проблема обычно не в команде, а в сетевом доступе pip к PyPI (прокси/фаервол).

Проверьте текущие настройки pip и переменные прокси:

```bash
python3 -m pip config list
env | grep -Ei 'http_proxy|https_proxy|no_proxy|PIP_INDEX_URL|PIP_EXTRA_INDEX_URL'
```

Если вы в корпоративной сети, используйте корректный зеркальный индекс (пример):

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt \
  --index-url https://pypi.org/simple
```

Если нужен корпоративный proxy, задайте его явно:

```bash
python3 -m pip install -r requirements.txt \
  --proxy http://<user>:<pass>@<proxy-host>:<port>
```

4. Создать `.env` файл:

```env
BOT_TOKEN=<ваш_токен_бота>
DATABASE_URL=postgresql://bot_user:<сложный_пароль>@localhost:5432/sales_tunnel_for_targets_bot_db
CALENDLY_PUBLIC_LINK=https://calendly.com/4davyd0vcreate/30min
GOOGLE_SHEETS_API_KEY=<google_api_key_для_sheets>
GOOGLE_SHEETS_SPREADSHEET_ID=<id_таблицы>
GOOGLE_SHEETS_RANGE=Content-events!A2:F
EXPORT_SHEETS_API_KEY=<google_api_key_для_sheets>
EXPORT_SHEETS_BEARER_TOKEN=<oauth_bearer_token_для_записи_в_sheets>
EXPORT_SHEETS_OAUTH_CLIENT_ID=<oauth_client_id_для_авторефреша>
EXPORT_SHEETS_OAUTH_CLIENT_SECRET=<oauth_client_secret_для_авторефреша>
EXPORT_SHEETS_OAUTH_REFRESH_TOKEN=<oauth_refresh_token_для_авторефреша>
EXPORT_SHEETS_OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token
EXPORT_SHEETS_SPREADSHEET_ID=<id_таблицы_для_выгрузки>
EXPORT_SHEETS_RANGE=users_export!A1:AR
EXPORT_SYNC_INTERVAL_MINUTES=5
```

## Настройка PostgreSQL

- Локальный PostgreSQL (Homebrew или Postgres.app).
- Создать пользователя и базу:

```sql
CREATE USER bot_user WITH PASSWORD '<сложный_пароль>';
CREATE DATABASE sales_tunnel_for_targets_bot_db OWNER bot_user;
```

- Актуальные таблицы создаются автоматически при запуске бота через `init_db()`.
- Устаревшие таблицы старого flow удаляются при инициализации схемы.

## Запуск бота

```bash
source .venv/bin/activate
python3 main.py
```

## Конфигурация

- Переменные окружения — `app/config.py`.
- Кнопки и inline/reply-клавиатуры — `app/keyboards.py`.
- FSM-состояния — `app/states.py`.
- Расчёты экономии — `app/scoring.py`.
- Хранение пользователей, событий и push-логов — `app/db.py`.
- Мероприятия из Google Sheets — `app/events.py`.
- Push-прогрев — `app/warmup.py`.
- Экспорт пользователей — `app/export_sync.py`.
