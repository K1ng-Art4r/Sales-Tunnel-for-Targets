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

## Railway: какая ветка деплоится

Короткий ответ: **обычно да, Railway по умолчанию деплоит `main`** (если в сервисе выбрана GitHub-интеграция и ветка не менялась вручную).

Важно: в Railway это настраивается в самом сервисе:

- `Project` → нужный `Service` → `Settings` → `Source / Repository` → `Branch`.
- Именно эта ветка является источником автодеплоя.

Если у вас сейчас выбрана `main`, то в прод будет запускаться код именно из `main`.
Если выбрана другая ветка (например, `develop`), деплоиться будет она.

## Docker

Проект можно собрать и запустить как Docker-контейнер. Образ запускает Telegram-бота командой `python main.py`.

### Сборка локально

```bash
docker build -t sales-tunnel-bot .
```

### Запуск локально

Перед запуском подготовьте `.env` с обязательными переменными окружения (`BOT_TOKEN`, `DATABASE_URL` и остальные интеграции при необходимости), затем выполните:

```bash
docker run --rm --env-file .env sales-tunnel-bot
```

Если PostgreSQL запущен на хост-машине, укажите в `DATABASE_URL` адрес, доступный из контейнера. Например, для Docker Desktop часто используют `host.docker.internal` вместо `localhost`.

## Перенос рабочей версии из GitHub в Azure DevOps

Ниже пример последовательности для публикации текущей рабочей версии в ветку Azure DevOps `Deploy_from_github`.

1. Убедиться, что локальная ветка содержит актуальную рабочую версию из GitHub:

```bash
git checkout main
git pull origin main
```

2. Добавить Azure DevOps как дополнительный remote. URL возьмите в Azure DevOps: `Repos` → `Clone` → `HTTPS`.

```bash
git remote add azure https://dev.azure.com/<organization>/<project>/_git/<repository>
```

Если remote `azure` уже есть, обновите URL:

```bash
git remote set-url azure https://dev.azure.com/<organization>/<project>/_git/<repository>
```

3. Проверить remotes:

```bash
git remote -v
```

4. Если Azure DevOps не принимает логин/пароль, подготовить HTTPS-аутентификацию через Personal Access Token (PAT). Для push по HTTPS в Azure DevOps обычно нужен PAT, а не пароль от аккаунта.

Создайте PAT в Azure DevOps: `User settings` → `Personal access tokens` → `New Token`. Минимальные права: `Code` → `Read & write`.

Если Git на macOS пишет `git: 'credential-manager-core' is not a git command`, значит в настройках указан старый credential helper. Переключите helper на системную связку ключей macOS:

```bash
git config --global --unset credential.helper
git config --global credential.helper osxkeychain
```

Очистите старые сохранённые учётные данные для Azure DevOps в `Keychain Access` / «Связка ключей» или выполните:

```bash
printf "protocol=https\nhost=woolman.visualstudio.com\n" | git credential-osxkeychain erase
```

5. Отправить текущую GitHub-версию в ветку Azure DevOps `Deploy_from_github`. В поле username можно указать e-mail/логин Azure DevOps, а в поле password вставить PAT:

```bash
git push azure main:Deploy_from_github
```

Если локальная рабочая ветка называется не `main`, замените `main` на нужное имя:

```bash
git push azure <local_branch>:Deploy_from_github
```

Если после этого аутентификация всё ещё падает, проверьте, что PAT не истёк, имеет права `Code: Read & write`, а ваш пользователь добавлен в проект Azure DevOps и имеет доступ к репозиторию.

Если push отклонён с сообщением `fetch first`, значит в Azure DevOps в ветке `Deploy_from_github` уже есть коммиты, которых нет локально. Сначала заберите remote-ветку и объедините её с локальной историей:

```bash
git fetch azure Deploy_from_github
git checkout main
git rebase azure/Deploy_from_github
git push azure main:Deploy_from_github
```

Если при rebase появятся конфликты, исправьте файлы, затем выполните:

```bash
git add <исправленные_файлы>
git rebase --continue
git push azure main:Deploy_from_github
```

Если Azure DevOps-ветку нужно именно перезаписать текущей GitHub-версией, делайте это только после согласования с командой, потому что remote-коммиты могут быть потеряны. Если локально уже начался merge/rebase и Git пишет `needs merge`, можно жёстко вернуть локальную ветку `main` к состоянию GitHub и затем жёстко отправить её в Azure DevOps:

```bash
git merge --abort 2>/dev/null || true
git rebase --abort 2>/dev/null || true
git fetch origin main
git checkout -B main origin/main
git clean -fd
git push --force azure main:Deploy_from_github
```

6. Если ветка `Deploy_from_github` в Azure DevOps защищена или уже содержит другую историю, сначала создайте pull request в Azure DevOps из вашей ветки в `Deploy_from_github`. Не используйте force push без согласования с командой.

7. В Azure DevOps настройте переменные окружения/секреты для контейнера или pipeline. Файл `.env` не нужно коммитить и не нужно класть в Docker-образ: значения задаются как secret variables в Azure DevOps Pipeline или как environment variables / application settings в сервисе, где запускается контейнер. Минимально обязательны:

- `BOT_TOKEN`
- `DATABASE_URL`

Дополнительно задайте переменные интеграций, которые используются в окружении:

- `CALENDLY_API_TOKEN`
- `CALENDLY_EVENT_TYPE_URI`
- `CALENDLY_PUBLIC_LINK`
- `MEETING_TIMEZONE`
- `GOOGLE_SHEETS_API_KEY`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_RANGE`
- `CONTENT_SHEETS_API_KEY`
- `CONTENT_SHEETS_SPREADSHEET_ID`
- `CONTENT_SHEETS_RANGE`
- `CONTENT_SCHEDULER_TIMEZONE`
- `EXPORT_SHEETS_API_KEY`
- `EXPORT_SHEETS_BEARER_TOKEN`
- `EXPORT_SHEETS_OAUTH_CLIENT_ID`
- `EXPORT_SHEETS_OAUTH_CLIENT_SECRET`
- `EXPORT_SHEETS_OAUTH_REFRESH_TOKEN`
- `EXPORT_SHEETS_OAUTH_TOKEN_URL`
- `EXPORT_SHEETS_SERVICE_ACCOUNT_EMAIL`
- `EXPORT_SHEETS_SERVICE_ACCOUNT_PRIVATE_KEY`
- `EXPORT_SHEETS_SERVICE_ACCOUNT_TOKEN_URI`
- `EXPORT_SHEETS_SPREADSHEET_ID`
- `EXPORT_SHEETS_RANGE`
- `EXPORT_SYNC_INTERVAL_MINUTES`

Если используется Azure Pipeline, секреты можно добавить в `Pipelines` → нужный pipeline → `Edit` → `Variables` → `New variable` → включить `Keep this value secret`. Если контейнер запускается в Azure App Service / Container Apps, эти же значения задаются в настройках приложения как environment variables.

### Как добавить переменные руками в Azure

Вариант зависит от того, где фактически запускается контейнер.

#### Azure DevOps Pipeline

1. Откройте Azure DevOps → `Pipelines`.
2. Выберите нужный pipeline.
3. Нажмите `Edit`.
4. Откройте `Variables`.
5. Нажмите `New variable`.
6. В `Name` укажите имя переменной, например `BOT_TOKEN`.
7. В `Value` вставьте значение из локального `.env`.
8. Для токенов, паролей, ключей и `DATABASE_URL` включите `Keep this value secret`.
9. Повторите для остальных переменных и сохраните pipeline.

#### Azure App Service

1. Откройте Azure Portal → нужный `App Service`.
2. Перейдите в `Settings` → `Environment variables` или `Configuration`.
3. В разделе application settings добавьте `Name` и `Value` для каждой переменной.
4. Сохраните изменения и перезапустите приложение, если Azure не предложит сделать это автоматически.

#### Azure Container Apps

1. Откройте Azure Portal → нужный `Container App`.
2. Перейдите в `Secrets` и добавьте секреты для чувствительных значений: `BOT_TOKEN`, `DATABASE_URL`, API-ключи и OAuth-токены.
3. Перейдите в настройки контейнера / revision.
4. В `Environment variables` добавьте переменные и для секретных значений выберите reference на созданный secret.
5. Сохраните изменения и создайте новую revision.

8. Для проверки Docker-сборки в Azure Pipeline можно использовать базовые команды:

```bash
docker build -t sales-tunnel-bot .
docker run --rm --env-file .env sales-tunnel-bot
```
