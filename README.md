# Sales Tunnel Bot MVP

Telegram-бот для первичной квалификации пользователей с возможностью ознакомиться с материалами, оценить бизнес и получить контактные данные команды.

## Функционал MVP

- /start — приветственное меню с 3 кнопками:
  1. Почитать материалы — присылает 5 локальных файлов/видео
  2. Оценить бизнес — развилка на трек 1 / трек 2 с минимальным опросником (роль, размер, срок, мотив)
  3. Связаться с нами — показывает контактные данные команды
- Финальные экраны треков с кнопкой “Оставить контакт”
- Контактный flow:
  - подтверждение использования данных
  - выбор формата контакта (email / Telegram / телефон)
  - запись данных в PostgreSQL
  - возможность добавить ещё один контакт или исправить существующий
  - кнопка “Меню” доступна только после завершения контактного flow
- Прогрев и вопросы закомментированы/отключены для MVP

## Структура проекта

Sales-Tunnel-for-Targets/

├── .env

├── .gitignore

├── main.py

└── app/

    ├── __init__.py

    ├── config.py

    ├── db.py

    ├── keyboards.py

    ├── materials.py

    ├── scoring.py

    ├── states.py

    └── handlers/

        ├── __init__.py
        
        └── start.py

## Установка

1. Клонировать репозиторий:
git clone <URL>
cd Sales-Tunnel-for-Targets

2. Создать виртуальное окружение и активировать:
python3 -m venv .venv
source .venv/bin/activate

3. Установить зависимости:
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt


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

4. Создать .env файл:
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
EXPORT_SHEETS_RANGE=users_export!A1:AB
EXPORT_SYNC_INTERVAL_MINUTES=5

## Настройка PostgreSQL

- Локальный PostgreSQL (Homebrew или Postgres.app)
- Создать пользователя и базу:
CREATE USER bot_user WITH PASSWORD '<сложный_пароль>';
CREATE DATABASE sales_tunnel_for_targets_bot_db OWNER bot_user;

- Таблицы создаются автоматически при запуске бота через init_db()

## Запуск бота

source .venv/bin/activate
python3 main.py

##Материалы

- 5 локальных файлов/видео находятся в materials/
- При нажатии Почитать материалы бот отправляет их пользователю

## Контактный flow

- После трека пользователь может оставить контакт
- Подтверждает использование данных
- Выбирает тип контакта: email / Telegram / телефон
- Вводит значение → сохраняется в БД
- Можно добавить ещё один контакт или исправить существующий
- После успешного ввода всех контактов кнопка “Меню” снова доступна

## Конфигурация

- Кнопки и тексты настраиваются в keyboards.py
- FSM состояния треков и контактов — states.py
- Расчёт fit/intent/status — scoring.py
- Материалы — materials.py
- Хранение и логирование — db.py

## Railway: какая ветка деплоится

Короткий ответ: **обычно да, Railway по умолчанию деплоит `main`** (если в сервисе выбрана GitHub-интеграция и ветка не менялась вручную).

Важно: в Railway это настраивается в самом сервисе:
- `Project` → нужный `Service` → `Settings` → `Source / Repository` → `Branch`.
- Именно эта ветка является источником автодеплоя.

Если у вас сейчас выбрана `main`, то в прод будет запускаться код именно из `main`.
Если выбрана другая ветка (например, `develop`), деплоиться будет она.
