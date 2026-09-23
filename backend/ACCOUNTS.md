# Аккаунты и профили, API 1.2

Backend хранит личные аккаунты, профили бизнеса/команды и связь владельца с профилем в SQLite. При регистрации создаётся один профиль и один владелец. Приглашения дополнительных участников, смена email, подтверждение email и восстановление пароля в эту версию не входят. Общий пароль команды не нужен и не предусмотрен.

## Подключение frontend

Все запросы выполняются с `credentials: 'include'`. Сервер сам устанавливает cookie `sana_session` с HttpOnly и SameSite=Lax; frontend не читает и не хранит её в localStorage. Пароль также нигде в браузерном хранилище не сохраняется.

1. После регистрации/входа сохранить `csrf_token` из ответа в памяти приложения.
2. При загрузке страницы вызвать `GET /api/auth/session`. Ответ восстанавливает пользователя, профиль и CSRF-токен; 401 означает, что нужно показать вход.
3. Во все изменяющие запросы передавать `X-CSRF-Token`. Это относится и к POST `/questions`, `/confirm`, `/publish`, `/compose`, откликам и этапам. Регистрация и вход не требуют предварительной сессии; их источник проверяется по Origin.
4. Для выхода вызвать POST `/api/auth/logout`, после 204 очистить клиентское состояние пользователя и его черновики. При 401 сессия уже недействительна: также очистить состояние.
5. При 403 `invalid_csrf` заново загрузить сессию. Не повторять автоматически запросы, создающие задачи или отклики.

```ts
const API = 'http://localhost:8000';
let csrfToken = '';

async function restoreSession() {
  const response = await fetch(`${API}/api/auth/session`, { credentials: 'include' });
  if (!response.ok) throw await response.json();
  const session = await response.json();
  csrfToken = session.csrf_token;
  return session.user;
}

async function updateProfile(description: string) {
  const response = await fetch(`${API}/api/profiles/me`, {
    method: 'PATCH', credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ description }),
  });
  if (!response.ok) throw await response.json();
  return response.json();
}
```

В dev используйте одинаковый hostname: `localhost:5173` + `localhost:8000` либо `127.0.0.1:5173` + `127.0.0.1:8000`. Не смешивайте localhost и 127.0.0.1: SameSite-cookie может не передаваться. Для размещения frontend и API на разных сайтах требуется отдельная настройка; текущая версия рассчитана на один сайт, допускаются разные порты.

## Endpoint-ы

| Метод и путь | Тело | Ответ |
|---|---|---|
| POST `/api/auth/register` | email, password, name, role, profile_name | 201 SessionResponse и cookie |
| POST `/api/auth/login` | email, password | 200 SessionResponse и новая cookie |
| GET `/api/auth/session` | — | 200 SessionResponse |
| POST `/api/auth/logout` | — | 204, текущая сессия отозвана |
| POST `/api/auth/password` | current_password, new_password | 204, все сессии отозваны, требуется новый вход |
| GET `/api/users/me` | — | 200 AccountResponse, приватные данные текущего пользователя |
| PATCH `/api/users/me` | name | 200 AccountResponse |
| GET `/api/profiles/me` | — | 200 PublicProfile |
| PATCH `/api/profiles/me` | изменённые поля профиля | 200 PublicProfile |
| GET `/api/profiles/{id}` | — | 200 PublicProfile; нужен вход |

Регистрация:

```json
{
  "email": "owner@example.com",
  "password": "choose-your-own-long-password",
  "name": "Алия",
  "role": "business",
  "profile_name": "Учебный центр"
}
```

`role` принимает только `business` или `team`. Пароль от 12 до 128 символов, без обрезки пробелов. Email нормализуется в нижний регистр; одинаковые email не создают разные аккаунты. `name` и `profile_name` обязательны и ограничены 120 символами.

SessionResponse содержит `user`, `csrf_token`, `expires_at` в Unix-секундах. AccountResponse содержит `id`, `email`, `name`, `profile`. Email доступен только самому пользователю. Его изменение через PATCH запрещено.

PublicProfile содержит:

- `id`, `role`, `team_id`, `name`, `description`, `industry`, `website`, `contact`;
- массивы `interests`, `skills`, `technologies`, `portfolio_urls`;
- `members` с отображаемыми именами и ролью `owner`, без email и идентификаторов личных аккаунтов;
- `team_points`, рассчитанные сервером по подтверждённым этапам.

Редактируются только поля из ProfileFields: название, описание, отрасль, сайт, публичный контакт, интересы, навыки, технологии и ссылки портфолио. PATCH сохраняет остальные поля. `null` вместо строки/массива, неизвестные поля и небезопасные URL отклоняются с 422. Для очистки использовать `""` либо `[]`; название не может быть пустым. Email для входа не переносится в публичный `contact` автоматически.

`id`, `role`, `team_id`, `members`, `team_points` нельзя изменить клиентским запросом. Владельца/команду задач и предложений сервер определяет через сессию и membership. `TaskResponse.owner_id` и `ProposalResponse.team_id` теперь указывают на профиль, а не на личный аккаунт. Для сравнения владения используйте `session.user.profile.id`; для просмотра автора вызывайте `/api/profiles/{id}`.

GET `/api/business/tasks` возвращает задачи собственного бизнес-профиля. GET `/api/team/proposals` возвращает предложения собственной команды, вложенные этапы и `team_points`. Бизнес продолжает получать все предложения к своей задаче. Существующий общий просмотр предложений команд по опубликованным задачам сохранён; приватность конкурирующих предложений не входит в эту миграцию.

## Сессии и защита

- Пароли хранятся как PBKDF2-HMAC-SHA256 с 600 000 итераций и отдельной случайной солью. Сравнение выполняется через constant-time compare. Параметры следуют [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- Сессия содержит 256 случайных бит; в БД сохраняется только SHA-256 токена. Срок действия семь дней, без автоматического продления. Выход отзывает текущую сессию, смена пароля все сессии пользователя.
- CSRF-токен связан с конкретной сессией. Для изменений проверяются токен и Origin. API-ответы имеют `Cache-Control: no-store`.
- Вход ограничен десятью попытками на email и 60 запросами с IP за 15 минут. Успешный вход сбрасывает счётчик email. Регистрация и смена пароля ограничены 20 запросами с IP за 15 минут; смена пароля также десятью попытками на аккаунт. Ограничения хранятся в SQLite, 429 содержит `Retry-After`.
- CORS разрешает только `FRONTEND_ORIGINS`, передача cookie включена. Для HTTPS установите `COOKIE_SECURE=true`. При reverse proxy корректно настройте доверенные proxy IP в Uvicorn: лимит использует `request.client.host`, а не самостоятельно прочитанный X-Forwarded-For.

Основные ошибки: 401 `authentication_required`, `invalid_session`, `invalid_credentials`; 403 `invalid_csrf`, `invalid_origin` и ошибки прав существующего API; 409 `email_taken`; 422 `validation_error`; 429 `too_many_attempts`. Ответы не содержат паролей, хешей или внутреннего текста исключений.

## Деморежим и миграция

По умолчанию `DEMO_MODE=false`: `X-Demo-Identity` не авторизует запросы, `/api/demo-identities` возвращает 404. Для старого демонстрационного frontend можно отдельно запустить backend с `DEMO_MODE=true`. Аккаунты и деморежим не следует смешивать в одной браузерной сессии: действительная cookie имеет приоритет над демозаголовком, недействительная cookie вызывает 401 и не разрешает обход через деморежим.

Новые таблицы добавляются при старте. Существующие задачи, отклики, этапы и баллы сохраняются. Старые демозаписи остаются за демопрофилями; регистрация не присваивает их новому пользователю. Для реальных аккаунтов создавайте собственные задачи. У демопрофилей нет общего пароля, вход по email за них невозможен. Авторизованные пользователи могут читать публичные демопрофили по ID даже при DEMO_MODE=false, чтобы видеть авторов карточек из seed; это не даёт права действовать от их имени.

Перед обновлением остановите сервер и сохраните резервную копию SQLite. Новые зависимости для аккаунтов не требуются. Тесты запускаются из корня проекта:

```powershell
py -m unittest discover -s backend -t .
```
