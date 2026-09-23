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
- Текущий шаг: следующий этап после push, публикация и каталог.
The API never calls an external AI provider in the MVP. The questions and compose endpoint use deterministic server-side validation and leave unknown fields empty. No API key is required or stored in Git.
