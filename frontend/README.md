# AI Sana frontend

Клиентская часть демонстрационной платформы AI Sana. Бизнес создаёт и публикует задачи, команда находит их, отправляет предложение и сдаёт результат этапа.

Текущий этап T001 включает запускаемое React-приложение, общую оболочку, четыре маршрута, переключение демопользователя и типизированный клиент согласованного backend API. Содержимое каталога, конструктора и кабинетов добавляется следующими задачами.

## Стек

- React 19
- TypeScript
- Vite
- React Router
- Manrope Variable через локальный пакет `@fontsource-variable/manrope`

Backend находится вне этой папки и разрабатывается отдельно. Frontend не хранит данные, не рассчитывает рейтинг задачи и не начисляет баллы команды.

## Требования

- Node.js с поддержкой Vite 8
- npm
- доступный backend AI Sana

Проверенная локальная среда: Node.js 24 и npm 11.

## Установка

```bash
cd frontend
npm install
```

## Переменные окружения

Скопируйте пример конфигурации:

```bash
cp .env.example .env
```

Для Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Доступная переменная:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Если переменная не задана, клиент использует `http://localhost:8000`.

Все переменные с префиксом `VITE_` попадают в браузерную сборку. Не помещайте туда API-ключ AI, токены и другие серверные секреты. Frontend обращается только к backend AI Sana, а backend выполняет вызовы AI со своим ключом.

## Запуск

Режим разработки:

```bash
npm run dev
```

Приложение будет доступно по адресу `http://localhost:5173`.

Production-сборка с проверкой TypeScript:

```bash
npm run build
```

Локальный просмотр production-сборки:

```bash
npm run preview
```

## Маршруты

| URL | Раздел |
|---|---|
| `/catalog` | Каталог опубликованных задач |
| `/constructor` | Конструктор задачи |
| `/business` | Кабинет бизнеса |
| `/team` | Кабинет команды |

Переходы работают на клиенте без полной перезагрузки страницы. Неизвестный маршрут перенаправляет в каталог.

## Демоидентичность

При старте приложение запрашивает `GET /api/demo-identities`. Ответ должен быть массивом:

```json
[
  {
    "id": "business-demo",
    "name": "ООО Ромашка",
    "role": "business",
    "team_id": null
  },
  {
    "id": "team-alpha",
    "name": "Команда Альфа",
    "role": "team",
    "team_id": "team-alpha"
  }
]
```

Выбранный ID сохраняется в `localStorage` под ключом `ai-sana.demo-identity`. Защищённые запросы отправляют заголовок:

```http
X-Demo-Identity: team-alpha
```

Роль не отправляется отдельным заголовком. Backend определяет её по ID. Это деморежим, а не production-аутентификация.

Если список идентичностей не загрузился, оболочка остаётся доступной и показывает действие `Повторить`. Пустой список блокирует переключатель без подстановки выдуманного пользователя.

## API-клиент

Типы контракта находятся в `src/api/types.ts`, клиент в `src/api/client.ts`.

Поддержаны методы для маршрутов:

- `GET /api/demo-identities`
- `POST /api/tasks`
- `GET /api/tasks/{id}`
- `PATCH /api/tasks/{id}`
- `POST /api/tasks/{id}/questions`
- `POST /api/tasks/{id}/compose`
- `POST /api/tasks/{id}/confirm`
- `POST /api/tasks/{id}/publish`
- `GET /api/tasks`
- `GET /api/business/tasks`
- `POST /api/tasks/{id}/proposals`
- `GET /api/tasks/{id}/proposals`
- `POST /api/proposals/{id}/decision`
- `GET /api/team/proposals`
- `POST /api/proposals/{id}/milestone`
- `POST /api/milestones/{id}/review`

Ошибочный ответ backend имеет форму:

```json
{
  "code": "confirmation_required",
  "message": "Сначала подтвердите задачу",
  "field_errors": {
    "title": "Заполните название"
  }
}
```

Клиент преобразует такой ответ в `ApiError` и сохраняет HTTP-статус, `code`, текст сообщения и `fieldErrors`. Если backend вернул не JSON, клиент сообщает об ошибке ответа вместо ложного успешного результата.

## Структура

```text
frontend/
  src/
    api/
      client.ts       типизированные HTTP-методы и ApiError
      types.ts        модели согласованного JSON-контракта
    app/
      App.tsx         оболочка, навигация и маршруты
      DemoSession.tsx загрузка и выбор демопользователя
    main.tsx          точка входа React
    styles.css        базовые стили оболочки и состояния фокуса
  .env.example        пример адреса backend
  index.html          HTML-точка входа
  package.json        команды и зависимости
  tsconfig.json       строгая проверка TypeScript
  vite.config.ts      конфигурация dev-сервера
```

## Проверка интеграции

1. Запустите backend на URL из `VITE_API_BASE_URL`.
2. Выполните `npm run dev`.
3. Откройте `/catalog`.
4. Убедитесь, что список демопользователей загрузился.
5. Переключите бизнес на команду и обратно.
6. Откройте все четыре раздела через навигацию.
7. В Network браузера проверьте, что защищённые API-запросы содержат актуальный `X-Demo-Identity`.
8. Выполните `npm run build` перед передачей изменений.

## Границы frontend

- Не добавлять клиентскую регистрацию.
- Не вызывать сторонний AI API из браузера.
- Не рассчитывать рейтинг задачи или баллы команды на клиенте.
- Не хранить серверные секреты в `.env` frontend.
- Не заменять данные backend статическими счётчиками перед сдачей.
- Тексты и демоданные согласовывать с QA/content.
