# AI Sana backend

## Run

From repository root on Windows:

```powershell
py -m pip install -r backend/requirements.txt
py -m uvicorn backend.main:app --reload --port 8000
```

SQLite is stored in `backend/sana.sqlite3`. Set `DATABASE_PATH` to use another file. The database is created on startup. Delete that file to reset demo data.

Use `X-Demo-Identity` on every API call. Valid values and roles are returned by `GET /api/demo-identities`.

The full JSON contract is in [`CONTRACT.md`](CONTRACT.md). FastAPI docs are available at `http://localhost:8000/docs`.

## Smoke request

```powershell
$headers = @{ "X-Demo-Identity" = "business-demo" }
Invoke-RestMethod http://localhost:8000/api/demo-identities
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/tasks -Headers $headers -ContentType "application/json" -Body '{"title":"Проблема","context":"Контекст","need":"Потребность"}'
```

## Progress log

- `9203618`: уточнён контракт API, статусы, поля ошибок и published snapshot.
- `ba2b318`: добавлено раздельное хранение текущего и опубликованного рейтинга задачи.
- Проверено: вопросы возвращают 5 вопросов для пустого черновика, compose сохраняет ответ пользователя и игнорирует неизвестные сведения.
- Проверено: каталог сортирует опубликованные задачи по рейтингу, принимает фильтры `topic` и `level`, а опубликованная задача с низким рейтингом остаётся доступна.
- Проверено: две команды могут отправить предложения, выбор одного предложения не изменяет статус второго (`selected` и `pending`).
- Проверено: команда не может подтвердить свой этап, бизнес получает `confirmed` и 10 баллов, повторная проверка остаётся идемпотентной.
- Проверено: полный сценарий прошёл через API, а опубликованная задача сохранилась после перезапуска Uvicorn и SQLite.
- OpenAI: подключены вопросы и compose через Chat Completions, JSON-валидация, таймаут 15 секунд без автоматических повторов. Проверены локальный режим, имитированный ответ провайдера, таймаут, неверная структура и отклонение неподтверждённых фактов. Реальный запрос не проверен: ключ не настроен.

## OpenAI

Создайте `.env` в корне репозитория по образцу `.env.example`:

```dotenv
AI_API_KEY=ваш_ключ
AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=15
```

`.env` исключён из Git. Не передавайте ключ frontend и не добавляйте его в отчёты.
Перезапустите сервер после изменения `.env`. Переменные процесса имеют приоритет над файлом.

`POST /api/tasks/{id}/questions` передаёт текущие поля и список отсутствующих полей.
Ответ модели: `{"questions":["Вопрос 1","Вопрос 2","Вопрос 3"]}`.
`POST /api/tasks/{id}/compose` передаёт текущие поля и массив `answers`.
Ответ модели должен содержать все 11 строковых полей карточки; неизвестное остаётся пустым.
Промпты находятся в `backend/ai.py`. Сборка использует извлечение цитат, а не свободное перефразирование: новые значения сверяются с текстом пользователя. Это ограничивает выдуманные значения, но не гарантирует правильную смысловую классификацию; человек проверяет карточку.

Без ключа, при ошибке OpenAI, таймауте или неверном JSON используется локальный режим. Формат API не меняется; в ответе пока нет признака использования fallback. Рейтинг, подтверждение и публикация не делегируются модели.
