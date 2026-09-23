from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from . import ai

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .rating import calculate_rating
from .schemas import (
    ComposeRequest, DecisionRequest, Identity, MilestoneRequest, ProposalCreate,
    ReviewRequest, TaskCreate, TaskFields, TaskPatch,
)

DB_PATH = Path(os.getenv("DATABASE_PATH", Path(__file__).with_name("sana.sqlite3")))
app = FastAPI(title="AI Sana Backend", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

IDENTITIES = [
    {"id": "business-demo", "name": "ООО Ромашка", "role": "business", "team_id": None},
    {"id": "team-alpha", "name": "Команда Альфа", "role": "team", "team_id": "team-alpha"},
    {"id": "team-beta", "name": "Команда Бета", "role": "team", "team_id": "team-beta"},
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, fields TEXT NOT NULL,
            published_fields TEXT NOT NULL DEFAULT '{}',
            published_rating TEXT,
            confirmed INTEGER NOT NULL DEFAULT 0, published INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1, rating TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, team_id TEXT NOT NULL,
            idea TEXT NOT NULL, plan TEXT NOT NULL, duration TEXT NOT NULL,
            prototype_url TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, description TEXT NOT NULL,
            result_url TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'submitted',
            comment TEXT NOT NULL DEFAULT '', points_awarded INTEGER NOT NULL DEFAULT 0
        );
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "published_fields" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN published_fields TEXT NOT NULL DEFAULT '{}'")
        if "published_rating" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN published_rating TEXT")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = {".".join(str(part) for part in error["loc"] if part != "body"): error["msg"] for error in exc.errors()}
    return JSONResponse(status_code=422, content={"code": "validation_error", "message": "Некорректное тело запроса", "field_errors": errors})

def fail(status: int, code: str, message: str, fields: dict | None = None):
    raise HTTPException(status, detail={"code": code, "message": message, **({"field_errors": fields} if fields else {})})


def identity(identity_id: str | None) -> dict:
    match = next((item for item in IDENTITIES if item["id"] == identity_id), None)
    if not match:
        fail(401, "invalid_identity", "Передайте допустимый X-Demo-Identity")
    return match


def task_row(task_id: str) -> sqlite3.Row:
    with db() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        fail(404, "task_not_found", "Задача не найдена")
    return row


def fields(row: sqlite3.Row) -> TaskFields:
    return TaskFields.model_validate(json.loads(row["fields"]))


def task_json(row: sqlite3.Row, published_view: bool = False) -> dict:
    source = row["published_fields"] if published_view and row["published_fields"] != "{}" else row["fields"]
    values = TaskFields.model_validate(json.loads(source)).model_dump()
    current_rating = json.loads(row["rating"])
    published_rating = json.loads(row["published_rating"]) if row["published_rating"] else None
    values.update({"id": row["id"], "owner_id": row["owner_id"], "confirmed": bool(row["confirmed"]),
                   "published": bool(row["published"]), "version": row["version"],
                   "rating": published_rating if published_view and published_rating else current_rating,
                   "published_rating": published_rating, "created_at": row["created_at"], "updated_at": row["updated_at"]})
    return values


def require_owner(row: sqlite3.Row, actor: dict) -> None:
    if row["owner_id"] != actor["id"]:
        fail(403, "not_owner", "Действие доступно только владельцу задачи")


def save_task(task_id: str, values: TaskFields, confirmed: bool, published: bool, version: int) -> sqlite3.Row:
    timestamp = now()
    rating = calculate_rating(values, confirmed=confirmed).model_dump_json()
    with db() as connection:
        connection.execute("UPDATE tasks SET fields=?, confirmed=?, published=?, version=?, rating=?, updated_at=? WHERE id=?",
                           (values.model_dump_json(), int(confirmed), int(published), version, rating, timestamp, task_id))
    return task_row(task_id)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/demo-identities", response_model=list[Identity])
def demo_identities() -> list[dict]:
    return IDENTITIES


@app.post("/api/tasks")
def create_task(payload: TaskCreate, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    if actor["role"] != "business":
        fail(403, "business_required", "Задачу может создать только бизнес")
    task_id, timestamp = str(uuid.uuid4()), now()
    values = TaskFields.model_validate(payload.model_dump())
    with db() as connection:
        connection.execute("INSERT INTO tasks (id, owner_id, fields, published_fields, published_rating, confirmed, published, version, rating, created_at, updated_at) VALUES (?, ?, ?, '{}', NULL, 0, 0, 1, ?, ?, ?)",
                           (task_id, actor["id"], values.model_dump_json(), calculate_rating(values).model_dump_json(), timestamp, timestamp))
    return task_json(task_row(task_id))
@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    row = task_row(task_id)
    if not row["published"] and row["owner_id"] != actor["id"]:
        fail(403, "private_task", "Черновик доступен только владельцу")
    return task_json(row, published_view=actor["id"] != row["owner_id"] and bool(row["published"]))


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: str, payload: TaskPatch, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    require_owner(row, actor)
    current = fields(row).model_dump()
    current.update(payload.model_dump(exclude_unset=True))
    return task_json(save_task(task_id, TaskFields.model_validate(current), False, bool(row["published"]), row["version"] + 1))


@app.post("/api/tasks/{task_id}/questions")
def questions(task_id: str, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    require_owner(row, actor)
    return {"questions": ai.questions(fields(row))}


@app.post("/api/tasks/{task_id}/compose")
def compose(task_id: str, payload: ComposeRequest, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    require_owner(row, actor)
    composed = ai.compose(fields(row), payload.answers)
    return task_json(save_task(task_id, composed, False, bool(row["published"]), row["version"] + 1))


@app.post("/api/tasks/{task_id}/confirm")
def confirm(task_id: str, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    require_owner(row, actor)
    return task_json(save_task(task_id, fields(row), True, bool(row["published"]), row["version"] + 1))


@app.post("/api/tasks/{task_id}/publish")
def publish(task_id: str, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    require_owner(row, actor)
    if not row["confirmed"]:
        fail(409, "confirmation_required", "Сначала подтвердите задачу")
    current = fields(row)
    rating = calculate_rating(current, confirmed=True)
    saved = save_task(task_id, current, True, True, row["version"] + 1)
    with db() as connection:
        connection.execute("UPDATE tasks SET published_fields=?, published_rating=? WHERE id=?", (current.model_dump_json(), rating.model_dump_json(), task_id))
    return task_json(task_row(task_id))


@app.get("/api/tasks")
def catalog(topic: str | None = None, level: str | None = Query(default=None), x_demo_identity: str | None = Header(default=None)) -> dict:
    identity(x_demo_identity)
    with db() as connection:
        rows = connection.execute("SELECT * FROM tasks WHERE published=1 ORDER BY json_extract(COALESCE(published_rating, rating), '$.total') DESC").fetchall()
    items = [task_json(row, published_view=True) for row in rows]
    if topic:
        items = [item for item in items if topic.lower() in item["topic"].lower()]
    if level:
        items = [item for item in items if item["rating"]["level"] == level]
    return {"items": items}
@app.get("/api/business/tasks")
def business_tasks(x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    if actor["role"] != "business":
        fail(403, "business_required", "Раздел доступен бизнесу")
    with db() as connection:
        rows = connection.execute("SELECT * FROM tasks WHERE owner_id=? ORDER BY updated_at DESC", (actor["id"],)).fetchall()
    return {"items": [task_json(row) for row in rows]}

@app.post("/api/tasks/{task_id}/proposals")
def create_proposal(task_id: str, payload: ProposalCreate, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, row = identity(x_demo_identity), task_row(task_id)
    if actor["role"] != "team":
        fail(403, "team_required", "Отклик может отправить только команда")
    if not row["published"]:
        fail(409, "task_not_published", "Задача не опубликована")
    proposal_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)", (proposal_id, task_id, actor["team_id"], payload.idea, payload.plan, payload.duration, payload.prototype_url, now()))
    return proposal_json(proposal_id)


def proposal_json(proposal_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if not row:
        fail(404, "proposal_not_found", "Предложение не найдено")
    return dict(row)


@app.get("/api/tasks/{task_id}/proposals")
def proposals(task_id: str, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor, task = identity(x_demo_identity), task_row(task_id)
    if actor["role"] == "business":
        require_owner(task, actor)
    with db() as connection:
        rows = connection.execute("SELECT * FROM proposals WHERE task_id=? ORDER BY created_at", (task_id,)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/proposals/{proposal_id}/decision")
def decision(proposal_id: str, payload: DecisionRequest, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    with db() as connection:
        proposal = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if not proposal:
        fail(404, "proposal_not_found", "Предложение не найдено")
    task = task_row(proposal["task_id"])
    require_owner(task, actor)
    with db() as connection:
        connection.execute("UPDATE proposals SET status=? WHERE id=?", (payload.decision, proposal_id))
    return proposal_json(proposal_id)


@app.get("/api/team/proposals")
def team_proposals(x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    if actor["role"] != "team":
        fail(403, "team_required", "Раздел доступен командам")
    with db() as connection:
        rows = connection.execute("SELECT * FROM proposals WHERE team_id=? ORDER BY created_at DESC", (actor["team_id"],)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/proposals/{proposal_id}/milestone")
def milestone(proposal_id: str, payload: MilestoneRequest, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    if actor["role"] != "team":
        fail(403, "team_required", "Результат отправляет команда")
    with db() as connection:
        proposal = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if not proposal or proposal["team_id"] != actor["team_id"]:
        fail(404, "proposal_not_found", "Предложение не найдено")
    if proposal["status"] != "selected":
        fail(409, "proposal_not_selected", "Результат можно отправить только по выбранному предложению")
    milestone_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO milestones VALUES (?, ?, ?, ?, 'submitted', '', 0)", (milestone_id, proposal_id, payload.description, payload.result_url))
    return milestone_json(milestone_id)


def milestone_json(milestone_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
    if not row:
        fail(404, "milestone_not_found", "Этап не найден")
    return dict(row)


@app.post("/api/milestones/{milestone_id}/review")
def review(milestone_id: str, payload: ReviewRequest, x_demo_identity: str | None = Header(default=None)) -> dict:
    actor = identity(x_demo_identity)
    if actor["role"] != "business":
        fail(403, "business_required", "Результат подтверждает бизнес")
    with db() as connection:
        row = connection.execute("SELECT m.*, p.task_id FROM milestones m JOIN proposals p ON p.id=m.proposal_id WHERE m.id=?", (milestone_id,)).fetchone()
    if not row:
        fail(404, "milestone_not_found", "Этап не найден")
    require_owner(task_row(row["task_id"]), actor)
    if row["status"] == "confirmed":
        return milestone_json(milestone_id)
    status = payload.decision
    points = 10 if status == "confirmed" else 0
    with db() as connection:
        connection.execute("UPDATE milestones SET status=?, comment=?, points_awarded=? WHERE id=?", (status, payload.comment, points, milestone_id))
    return milestone_json(milestone_id)
