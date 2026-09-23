from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import ai
from .rating import calculate_rating
from .schemas import (
    ComposeRequest, DecisionRequest, ErrorResponse, Identity, Level,
    MilestoneRequest, MilestoneResponse, ProposalCreate, ProposalList,
    ProposalResponse, QuestionResponse, ReviewRequest, TaskCreate, TaskFields,
    TaskList, TaskPatch, TaskResponse, TeamProposalList,
)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DB_PATH = Path(os.getenv('DATABASE_PATH', Path(__file__).with_name('sana.sqlite3')))
IDENTITIES = [Identity.model_validate(item).model_dump() for item in json.loads((ROOT / 'fixtures/demo-identities.json').read_text(encoding='utf-8'))]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db(write: bool = False):
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        if write:
            connection.execute('BEGIN IMMEDIATE')
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, fields TEXT NOT NULL,
            published_fields TEXT NOT NULL DEFAULT '{}', published_rating TEXT,
            confirmed INTEGER NOT NULL DEFAULT 0, published INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1, rating TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), team_id TEXT NOT NULL,
            idea TEXT NOT NULL, plan TEXT NOT NULL, duration TEXT NOT NULL,
            prototype_url TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES proposals(id), description TEXT NOT NULL,
            result_url TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'submitted',
            comment TEXT NOT NULL DEFAULT '', points_awarded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS milestone_legacy_archive (
            id TEXT PRIMARY KEY, record TEXT NOT NULL, archived_at TEXT NOT NULL
        );
        ''')
    with db(write=True) as connection:
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(tasks)')}
        for name, definition in (
            ('published_fields', "TEXT NOT NULL DEFAULT '{}'"),
            ('published_rating', 'TEXT'), ('published_version', 'INTEGER'),
            ('published_updated_at', 'TEXT'),
        ):
            if name not in columns:
                connection.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
        for row in connection.execute('SELECT * FROM tasks').fetchall():
            current = TaskFields.model_validate_json(row['fields'])
            connection.execute('UPDATE tasks SET rating=? WHERE id=?', (calculate_rating(current, bool(row['confirmed'])).model_dump_json(), row['id']))
            if row['published']:
                snapshot = row['published_fields'] if row['published_fields'] != '{}' else row['fields']
                rating = calculate_rating(TaskFields.model_validate_json(snapshot), True).model_dump_json()
                connection.execute(
                    'UPDATE tasks SET published_fields=?, published_rating=?, published_version=COALESCE(published_version,version), published_updated_at=COALESCE(published_updated_at,updated_at) WHERE id=?',
                    (snapshot, rating, row['id']),
                )
        duplicates = connection.execute('SELECT proposal_id FROM milestones GROUP BY proposal_id HAVING COUNT(*)>1').fetchall()
        for group in duplicates:
            rows = connection.execute("SELECT * FROM milestones WHERE proposal_id=? ORDER BY (status='confirmed') DESC, rowid DESC", (group['proposal_id'],)).fetchall()
            for row in rows:
                connection.execute('INSERT OR IGNORE INTO milestone_legacy_archive VALUES (?,?,?)', (row['id'], json.dumps(dict(row), ensure_ascii=False), now()))
            for row in rows[1:]:
                connection.execute('DELETE FROM milestones WHERE id=?', (row['id'],))
        connection.execute("UPDATE milestones SET points_awarded=CASE WHEN status='confirmed' THEN 10 ELSE 0 END")
        connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS one_milestone_per_proposal ON milestones(proposal_id)')
        connection.execute('CREATE INDEX IF NOT EXISTS proposals_task ON proposals(task_id)')
        connection.execute('CREATE INDEX IF NOT EXISTS proposals_team ON proposals(team_id)')


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title='AI Sana Backend', version='1.1.0', lifespan=lifespan,
              responses={status: {'model': ErrorResponse} for status in (401, 403, 404, 409, 422, 500, 503)})
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], expose_headers=['X-AI-Source'])


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'http_error', 'message': str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = {'.'.join(str(part) for part in error['loc'] if part != 'body') or 'body': error['msg'] for error in exc.errors()}
    return JSONResponse(status_code=422, content={'code':'validation_error', 'message':'Некорректный запрос', 'field_errors':errors})


@app.exception_handler(sqlite3.OperationalError)
async def database_error(_: Request, exc: sqlite3.OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={'code':'database_unavailable', 'message':'База временно недоступна; повторите запрос'})


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # Starlette re-raises unexpected errors after sending this response; Uvicorn logs them.
    return JSONResponse(status_code=500, content={'code':'internal_error', 'message':'Внутренняя ошибка сервера'})


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={'code':code, 'message':message})


def identity(identity_id: str | None) -> dict:
    actor = next((item for item in IDENTITIES if item['id'] == identity_id), None)
    if actor is None:
        fail(401, 'invalid_identity', 'Передайте допустимый X-Demo-Identity')
    return actor


def require_role(actor: dict, role: str):
    if actor['role'] != role:
        fail(403, role + '_required', 'Действие недоступно выбранной роли')


def require_owner(row: sqlite3.Row, actor: dict):
    if actor['role'] != 'business' or row['owner_id'] != actor['id']:
        fail(403, 'not_owner', 'Действие доступно только владельцу задачи')


def task_row(connection, task_id: str):
    row = connection.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
    if row is None:
        fail(404, 'task_not_found', 'Задача не найдена')
    return row


def proposal_row(connection, proposal_id: str):
    row = connection.execute('SELECT * FROM proposals WHERE id=?', (proposal_id,)).fetchone()
    if row is None:
        fail(404, 'proposal_not_found', 'Предложение не найдено')
    return row


def task_json(row, published_view=False):
    source = row['published_fields'] if published_view else row['fields']
    values = TaskFields.model_validate_json(source).model_dump()
    published_rating = json.loads(row['published_rating']) if row['published_rating'] else None
    values.update(id=row['id'], owner_id=row['owner_id'], confirmed=True if published_view else bool(row['confirmed']),
                  published=bool(row['published']), version=row['published_version'] if published_view else row['version'],
                  rating=published_rating if published_view else json.loads(row['rating']), published_rating=published_rating,
                  created_at=row['created_at'], updated_at=row['published_updated_at'] if published_view else row['updated_at'])
    return values


def proposal_json(connection, row):
    value = dict(row)
    milestone = connection.execute('SELECT * FROM milestones WHERE proposal_id=?', (row['id'],)).fetchone()
    value['milestone'] = dict(milestone) if milestone else None
    return value


def update_fields(connection, row, values: TaskFields):
    connection.execute('UPDATE tasks SET fields=?, confirmed=0, version=version+1, rating=?, updated_at=? WHERE id=?',
                       (values.model_dump_json(), calculate_rating(values).model_dump_json(), now(), row['id']))
    return task_json(task_row(connection, row['id']))


@app.get('/api/health')
def health() -> dict[str, str]:
    return {'status':'ok'}


@app.get('/api/demo-identities', response_model=list[Identity])
def demo_identities():
    return IDENTITIES


@app.post('/api/tasks', response_model=TaskResponse)
def create_task(payload: TaskCreate, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'business')
    task_id, timestamp = str(uuid.uuid4()), now()
    values = TaskFields.model_validate(payload.model_dump())
    with db(write=True) as connection:
        connection.execute('INSERT INTO tasks (id,owner_id,fields,rating,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                           (task_id, actor['id'], values.model_dump_json(), calculate_rating(values).model_dump_json(), timestamp, timestamp))
        return task_json(task_row(connection, task_id))


@app.get('/api/tasks/{task_id}', response_model=TaskResponse)
def get_task(task_id: str, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db() as connection:
        row = task_row(connection, task_id)
        if row['owner_id'] != actor['id'] and not row['published']:
            fail(403, 'private_task', 'Черновик доступен только владельцу')
        return task_json(row, published_view=row['owner_id'] != actor['id'])


@app.patch('/api/tasks/{task_id}', response_model=TaskResponse)
def patch_task(task_id: str, payload: TaskPatch, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db(write=True) as connection:
        row = task_row(connection, task_id)
        require_owner(row, actor)
        current = TaskFields.model_validate_json(row['fields']).model_dump()
        changed = payload.model_dump(exclude_unset=True)
        if not changed or all(current[key] == value for key, value in changed.items()):
            return task_json(row)
        current.update(changed)
        return update_fields(connection, row, TaskFields.model_validate(current))


@app.post('/api/tasks/{task_id}/questions', response_model=QuestionResponse)
def questions(task_id: str, response: Response, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db() as connection:
        row = task_row(connection, task_id)
        require_owner(row, actor)
    result = ai.questions(TaskFields.model_validate_json(row['fields']))
    response.headers['X-AI-Source'] = ai.last_source.get()
    return {'questions':result}


@app.post('/api/tasks/{task_id}/compose', response_model=TaskResponse)
def compose(task_id: str, payload: ComposeRequest, response: Response, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db() as connection:
        row = task_row(connection, task_id)
        require_owner(row, actor)
    result = ai.compose(TaskFields.model_validate_json(row['fields']), payload.answers)
    response.headers['X-AI-Source'] = ai.last_source.get()
    with db(write=True) as connection:
        current = task_row(connection, task_id)
        if current['version'] != row['version']:
            fail(409, 'task_changed', 'Задача изменена; загрузите актуальную версию')
        return update_fields(connection, current, result)


@app.post('/api/tasks/{task_id}/confirm', response_model=TaskResponse)
def confirm(task_id: str, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db(write=True) as connection:
        row = task_row(connection, task_id)
        require_owner(row, actor)
        if not row['confirmed']:
            rating = calculate_rating(TaskFields.model_validate_json(row['fields']), True)
            connection.execute('UPDATE tasks SET confirmed=1,rating=?,version=version+1,updated_at=? WHERE id=?', (rating.model_dump_json(), now(), task_id))
        return task_json(task_row(connection, task_id))


@app.post('/api/tasks/{task_id}/publish', response_model=TaskResponse)
def publish(task_id: str, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db(write=True) as connection:
        row = task_row(connection, task_id)
        require_owner(row, actor)
        if not row['confirmed']:
            fail(409, 'confirmation_required', 'Сначала подтвердите задачу')
        if not row['published'] or row['published_fields'] != row['fields'] or row['published_rating'] != row['rating']:
            timestamp = now()
            connection.execute('UPDATE tasks SET published=1,published_fields=fields,published_rating=rating,version=version+1,published_version=version+1,updated_at=?,published_updated_at=? WHERE id=?', (timestamp, timestamp, task_id))
        return task_json(task_row(connection, task_id))


@app.get('/api/tasks', response_model=TaskList)
def catalog(topic: str | None = None, level: Level | None = None, x_demo_identity: str | None = Header(default=None)):
    identity(x_demo_identity)
    with db() as connection:
        rows = connection.execute("SELECT * FROM tasks WHERE published=1 ORDER BY json_extract(published_rating,'$.total') DESC, id ASC").fetchall()
    items = [task_json(row, True) for row in rows]
    if topic and topic.strip():
        items = [item for item in items if topic.strip().casefold() in item['topic'].casefold()]
    if level:
        items = [item for item in items if item['rating']['level'] == level]
    return {'items':items}


@app.get('/api/business/tasks', response_model=TaskList)
def business_tasks(x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'business')
    with db() as connection:
        return {'items':[task_json(row) for row in connection.execute('SELECT * FROM tasks WHERE owner_id=? ORDER BY updated_at DESC,id', (actor['id'],))]}


@app.post('/api/tasks/{task_id}/proposals', response_model=ProposalResponse)
def create_proposal(task_id: str, payload: ProposalCreate, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'team')
    with db(write=True) as connection:
        row = task_row(connection, task_id)
        if not row['published']:
            fail(409, 'task_not_published', 'Задача не опубликована')
        proposal_id = str(uuid.uuid4())
        connection.execute('INSERT INTO proposals (id,task_id,team_id,idea,plan,duration,prototype_url,created_at) VALUES (?,?,?,?,?,?,?,?)',
                           (proposal_id, task_id, actor['team_id'], payload.idea, payload.plan, payload.duration, payload.prototype_url, now()))
        return proposal_json(connection, proposal_row(connection, proposal_id))


@app.get('/api/tasks/{task_id}/proposals', response_model=ProposalList)
def proposals(task_id: str, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db() as connection:
        row = task_row(connection, task_id)
        if actor['role'] == 'business':
            require_owner(row, actor)
        elif not row['published']:
            fail(403, 'private_task', 'Черновик доступен только владельцу')
        return {'items':[proposal_json(connection, item) for item in connection.execute('SELECT * FROM proposals WHERE task_id=? ORDER BY created_at,id', (task_id,)).fetchall()]}


@app.post('/api/proposals/{proposal_id}/decision', response_model=ProposalResponse)
def decision(proposal_id: str, payload: DecisionRequest, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    with db(write=True) as connection:
        proposal = proposal_row(connection, proposal_id)
        require_owner(task_row(connection, proposal['task_id']), actor)
        milestone = connection.execute('SELECT id FROM milestones WHERE proposal_id=?', (proposal_id,)).fetchone()
        if milestone and payload.decision != proposal['status']:
            fail(409, 'proposal_in_progress', 'После отправки результата выбор команды нельзя изменить')
        connection.execute('UPDATE proposals SET status=? WHERE id=?', (payload.decision, proposal_id))
        return proposal_json(connection, proposal_row(connection, proposal_id))


@app.get('/api/team/proposals', response_model=TeamProposalList)
def team_proposals(x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'team')
    with db() as connection:
        rows = connection.execute('SELECT * FROM proposals WHERE team_id=? ORDER BY created_at DESC,id', (actor['team_id'],)).fetchall()
        items = [proposal_json(connection, row) for row in rows]
        points = sum(item['milestone']['points_awarded'] for item in items if item['milestone'])
        return {'items':items, 'team_points':points}


@app.post('/api/proposals/{proposal_id}/milestone', response_model=MilestoneResponse)
def milestone(proposal_id: str, payload: MilestoneRequest, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'team')
    with db(write=True) as connection:
        proposal = proposal_row(connection, proposal_id)
        if proposal['team_id'] != actor['team_id']:
            fail(403, 'not_team_owner', 'Результат отправляет автор предложения')
        if proposal['status'] != 'selected':
            fail(409, 'proposal_not_selected', 'Предложение не выбрано')
        previous = connection.execute('SELECT * FROM milestones WHERE proposal_id=?', (proposal_id,)).fetchone()
        if previous:
            if previous['status'] != 'changes_requested':
                if previous['description'] == payload.description and previous['result_url'] == payload.result_url:
                    return dict(previous)
                fail(409, 'milestone_locked', 'Результат можно изменить только после возврата на доработку')
            milestone_id = previous['id']
            connection.execute("UPDATE milestones SET description=?,result_url=?,status='submitted',comment='',points_awarded=0 WHERE id=?", (payload.description, payload.result_url, milestone_id))
        else:
            milestone_id = str(uuid.uuid4())
            connection.execute('INSERT INTO milestones (id,proposal_id,description,result_url) VALUES (?,?,?,?)', (milestone_id, proposal_id, payload.description, payload.result_url))
        return dict(connection.execute('SELECT * FROM milestones WHERE id=?', (milestone_id,)).fetchone())


@app.post('/api/milestones/{milestone_id}/review', response_model=MilestoneResponse)
def review(milestone_id: str, payload: ReviewRequest, x_demo_identity: str | None = Header(default=None)):
    actor = identity(x_demo_identity)
    require_role(actor, 'business')
    with db(write=True) as connection:
        row = connection.execute('SELECT * FROM milestones WHERE id=?', (milestone_id,)).fetchone()
        if row is None:
            fail(404, 'milestone_not_found', 'Этап не найден')
        proposal = proposal_row(connection, row['proposal_id'])
        require_owner(task_row(connection, proposal['task_id']), actor)
        if proposal['status'] != 'selected':
            fail(409, 'proposal_not_selected', 'Предложение не выбрано')
        if row['status'] == payload.decision:
            return dict(row)
        if row['status'] != 'submitted':
            fail(409, 'invalid_transition', 'Ожидается отправленный результат')
        connection.execute('UPDATE milestones SET status=?,comment=?,points_awarded=? WHERE id=?', (payload.decision, payload.comment, 10 if payload.decision == 'confirmed' else 0, milestone_id))
        return dict(connection.execute('SELECT * FROM milestones WHERE id=?', (milestone_id,)).fetchone())
