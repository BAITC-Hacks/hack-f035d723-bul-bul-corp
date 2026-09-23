# Backend API contract

Base URL: `http://localhost:8000`. JSON is UTF-8. Every request that acts as a demo user sends `X-Demo-Identity: <id>`. The server accepts only IDs returned by `GET /api/demo-identities`; this is demo identity selection, not production authentication.

## Identities

`GET /api/demo-identities` returns:

```json
[
  {"id":"business-demo","name":"ООО Ромашка","role":"business","team_id":null},
  {"id":"team-alpha","name":"Команда Альфа","role":"team","team_id":"team-alpha"},
  {"id":"team-beta","name":"Команда Бета","role":"team","team_id":"team-beta"}
]
```

## Empty and required fields

Task text fields are always present in task responses and default to `""`. The task create body may omit any field. The fields are `title`, `topic`, `context`, `need`, `users`, `data_materials`, `constraints`, `expected_result`, `success_criteria`, `contact`, and `consultation`.

Proposal fields `idea`, `plan`, and `duration` are required and must be non-empty. `prototype_url` is optional and defaults to `""`. Milestone `description` is required and must be non-empty. `result_url` and review `comment` are optional and default to `""`. PATCH fields are optional; omitted keys stay unchanged, while explicit empty strings clear fields.

Task text fields reject explicit `null` with HTTP 422 and `validation_error`. Use `""` to clear a value.

## Task response

All task endpoints return the task object:

```json
{
  "id":"uuid", "owner_id":"business-demo", "title":"", "topic":"",
  "context":"", "need":"", "users":"", "data_materials":"",
  "constraints":"", "expected_result":"", "success_criteria":"",
  "contact":"", "consultation":"", "confirmed":false, "published":false,
  "version":1, "rating": {"total":0,"level":"draft","categories":[],"missing":[]},
  "created_at":"ISO-8601", "updated_at":"ISO-8601"
}
```

## Status strings

- Task flags: `confirmed` and `published` are booleans. A draft is `confirmed=false`; publication never occurs without confirmation. Editing any draft or published task sets `confirmed=false` and keeps the previous `published` value. Therefore a published task can have unconfirmed edits while the catalog continues showing the last saved published fields in this MVP contract. `POST /confirm` confirms the current editable fields and recalculates the rating. `POST /publish` requires confirmation.
- Proposal `status`: `pending`, `selected`, `rejected`. The business can select or reject any proposal independently. Selecting one never changes another proposal.
- Milestone `status`: `submitted`, `confirmed`, `changes_requested`. A confirmed milestone awards exactly 10 points once. Resubmission is represented by a new milestone; review of an already confirmed milestone is idempotent.

## Endpoints

- `POST /api/tasks`: business creates a draft; body is the task fields object.
- `GET /api/tasks/{id}`: owner sees drafts; everyone with a valid identity can see published tasks.
- `PATCH /api/tasks/{id}`: owner updates any subset of task fields.
- `POST /api/tasks/{id}/questions`: owner receives `{ "questions": [string, ...] }`, at least three relevant questions for missing information.
- `POST /api/tasks/{id}/compose`: owner sends `{ "answers": [{"question":string,"answer":string}] }`; unknown information stays empty and no facts are invented.
- `POST /api/tasks/{id}/confirm`: owner confirms and receives the task with calculated rating.
- `POST /api/tasks/{id}/publish`: owner publishes a confirmed task.
- `GET /api/tasks?topic=<text>&level=<draft|working|ready|priority>`: catalog, published tasks only, descending rating total. No artificial proposal limit.
- `GET /api/business/tasks`: current business's tasks.
- `POST /api/tasks/{id}/proposals`: team body `{ "idea":string,"plan":string,"duration":string,"prototype_url":string }`.
- `GET /api/tasks/{id}/proposals`: business owner or any team reads proposals.
- `POST /api/proposals/{id}/decision`: owner body `{ "decision":"selected"|"rejected" }`.
- `GET /api/team/proposals`: current team's proposals.
- `POST /api/proposals/{id}/milestone`: selected team body `{ "description":string,"result_url":string }`.
- `POST /api/milestones/{id}/review`: task owner body `{ "decision":"confirmed"|"changes_requested","comment":string }`.

## Rating

Only confirmation scores fields. Before confirmation `total` is zero, but `missing` and category bases explain what is absent. Categories and maximums are: `context_need` 20, `data_materials` 20, `expected_result` 15, `success_criteria` 15, `constraints` 10, `users` 10, `contact_consultation` 10. Empty or whitespace-only values score zero. Compound categories receive proportional points per populated subfield. Success criteria receive points only when a number and an explicit time, currency, percentage, quantity, or metric marker is present. Levels are `draft` 0-39, `working` 40-69, `ready` 70-89, `priority` 90-100. The response contains `total`, `level`, `categories[]` with `key`, `label`, `points`, `max_points`, `basis[]`, and `missing[]`.

## Errors

The API returns HTTP status plus this JSON shape, never a successful response with an error:

```json
{"code":"confirmation_required","message":"Сначала подтвердите задачу","field_errors":{"title":"..."}}
```

`field_errors` is omitted when no field-level details exist. Typical codes: `invalid_identity` (401), `not_owner` (403), `business_required` (403), `team_required` (403), `private_task` (403), `task_not_found` (404), `proposal_not_found` (404), `milestone_not_found` (404), `confirmation_required` (409), `task_not_published` (409), and `proposal_not_selected` (409).

## Published snapshot fields

The task response contains `published_rating`, null until publication. Owner views expose the editable fields, rating, confirmation flag, version and timestamp. Catalog and non-owner views expose the complete published snapshot: fields, rating, `confirmed=true`, publication version and timestamp. PATCH and confirm never modify that snapshot. Publish copies confirmed fields and rating atomically. Concurrent changes detected during save/publish return HTTP 409 with `code=task_changed`; reload before retrying.

Existing databases are upgraded at startup. Historical publication timestamps/versions were not previously stored; migration initializes those from the available task metadata. Subsequent publications preserve the exact snapshot.

```json
{
  "rating": {
    "total": 0,
    "level": "draft",
    "categories": [
      {
        "key": "context_need",
        "label": "Контекст и потребность",
        "points": 0,
        "max_points": 20,
        "basis": ["Заполнено полей: 0 из 2"]
      }
    ],
    "missing": ["Контекст и потребность"]
  },
  "published_rating": null
}
```

## Non-task response bodies

`POST /questions` returns `{ "questions": ["...", "...", "..."] }`.

`POST /proposals` and `POST /decision` return:

```json
{
  "id": "uuid", "task_id": "uuid", "team_id": "team-alpha",
  "idea": "...", "plan": "...", "duration": "...",
  "prototype_url": "", "status": "pending", "created_at": "ISO-8601"
}
```

`POST /milestone` and `POST /review` return:

```json
{
  "id": "uuid", "proposal_id": "uuid", "description": "...",
  "result_url": "", "status": "submitted", "comment": "",
  "points_awarded": 0
}
```
