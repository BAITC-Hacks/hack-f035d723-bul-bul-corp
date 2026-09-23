"""SQLite-backed personal accounts, public profiles and revocable cookie sessions."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.security import APIKeyCookie

from .account_schemas import (
    AccountResponse, LoginRequest, PasswordChange, ProfileFields, ProfilePatch,
    PublicProfile, RegisterRequest, SessionResponse, UserPatch,
)

router = APIRouter(tags=['Accounts'])
COOKIE_NAME = 'sana_session'
session_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)
SESSION_SECONDS = 7 * 24 * 60 * 60
PASSWORD_ITERATIONS = 600_000
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def database(write=False):
    # The application owns the database path, including isolated test databases.
    from .main import db
    return db(write=write)


def init_tables(connection):
    for statement in (
        '''CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            password_hash TEXT NOT NULL, created_at INTEGER NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('business','team')),
            fields TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS memberships (
            user_id TEXT PRIMARY KEY REFERENCES accounts(id),
            profile_id TEXT NOT NULL REFERENCES profiles(id),
            role TEXT NOT NULL CHECK(role='owner'))''',
        '''CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(id),
            expires_at INTEGER NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id)',
        'CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)',
        '''CREATE TABLE IF NOT EXISTS auth_attempts (
            key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at INTEGER NOT NULL)''',
    ):
        connection.execute(statement)


def demo_enabled():
    return os.getenv('DEMO_MODE', '').lower() in {'1', 'true', 'yes'}


def frontend_origins():
    return [value.strip().rstrip('/') for value in os.getenv(
        'FRONTEND_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173'
    ).split(',') if value.strip() and value.strip() != '*']


def error(status, code, message, headers=None):
    raise HTTPException(status, detail={'code': code, 'message': message}, headers=headers)


def check_origin(request: Request):
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get('origin')
    allowed = {str(request.base_url).rstrip('/'), *frontend_origins()}
    if (origin is not None and origin not in allowed) or (
        origin is None and request.headers.get('sec-fetch-site') == 'cross-site'
    ):
        error(403, 'invalid_origin', 'Источник запроса не разрешён')


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token):
    return hmac.new(token.encode(), b'ai-sana-csrf', hashlib.sha256).hexdigest()


def hash_password(password):
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PASSWORD_ITERATIONS)
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${value.hex()}'


def verify_password(password, stored):
    _, iterations, salt, expected = stored.split('$')
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(value.hex(), expected)


# Unknown accounts still run the same password derivation before rejecting login.
DUMMY_HASH = f'pbkdf2_sha256${PASSWORD_ITERATIONS}${"00" * 16}${"00" * 32}'


def rate_limit(request, action, email=None):
    current = int(time.time())
    host = request.client.host if request.client else 'unknown'
    limits = [(f'{action}:ip:{digest(host)}', 60 if action == 'login' else 20)]
    if email is not None:
        limits.append((f'{action}:email:{digest(email)}', 10))
    with database(write=True) as connection:
        connection.execute('DELETE FROM auth_attempts WHERE expires_at<=?', (current,))
        for key, maximum in limits:
            row = connection.execute('SELECT * FROM auth_attempts WHERE key=?', (key,)).fetchone()
            if row and row['count'] >= maximum:
                error(429, 'too_many_attempts', 'Слишком много попыток. Попробуйте позже.',
                      {'Retry-After': str(row['expires_at'] - current)})
        for key, _ in limits:
            connection.execute('''INSERT INTO auth_attempts VALUES (?,1,?)
                ON CONFLICT(key) DO UPDATE SET count=count+1''', (key, current + 900))


def profile_json(connection, profile_id):
    row = connection.execute('SELECT * FROM profiles WHERE id=?', (profile_id,)).fetchone()
    if row is None:
        error(404, 'profile_not_found', 'Профиль не найден')
    members = connection.execute('''SELECT a.name, m.role FROM memberships m
        JOIN accounts a ON a.id=m.user_id WHERE m.profile_id=? ORDER BY a.id''', (profile_id,)).fetchall()
    points = connection.execute('''SELECT COALESCE(SUM(m.points_awarded),0) FROM milestones m
        JOIN proposals p ON p.id=m.proposal_id WHERE p.team_id=? AND m.status='confirmed' ''',
        (profile_id,)).fetchone()[0]
    return {**json.loads(row['fields']), 'id': profile_id, 'role': row['role'],
            'team_id': profile_id if row['role'] == 'team' else None,
            'members': [dict(member) for member in members], 'team_points': points}


def account_json(connection, user_id):
    row = connection.execute('''SELECT a.id,a.email,a.name,m.profile_id FROM accounts a
        JOIN memberships m ON m.user_id=a.id WHERE a.id=?''', (user_id,)).fetchone()
    if row is None:
        error(401, 'invalid_session', 'Войдите в аккаунт')
    return {'id': row['id'], 'email': row['email'], 'name': row['name'],
            'profile': profile_json(connection, row['profile_id'])}


def require_session(request: Request, token: str | None = Depends(session_cookie),
                    x_csrf_token: str | None = Header(default=None)):
    check_origin(request)
    if not token or len(token) != 43:
        error(401, 'authentication_required', 'Войдите в аккаунт')
    with database() as connection:
        session = connection.execute('SELECT * FROM sessions WHERE token_hash=? AND expires_at>?',
                                     (digest(token), int(time.time()))).fetchone()
        if session is None:
            error(401, 'invalid_session', 'Сессия истекла или завершена. Войдите снова.')
        user = account_json(connection, session['user_id'])
    if request.method not in SAFE_METHODS and not hmac.compare_digest(
        (x_csrf_token or '').encode(), csrf_token(token).encode()
    ):
        error(403, 'invalid_csrf', 'Обновите сессию и повторите запрос')
    return {'user': user, 'csrf_token': csrf_token(token), 'expires_at': session['expires_at']}


def current_identity(request: Request, x_demo_identity: str | None = Header(default=None),
                     token: str | None = Depends(session_cookie), x_csrf_token: str | None = Header(default=None)):
    # A stale session must not fall back to a supplied demo identity.
    if COOKIE_NAME in request.cookies:
        return require_session(request, token, x_csrf_token)['user']['profile']
    if demo_enabled() and x_demo_identity:
        check_origin(request)
        from .main import IDENTITIES
        actor = next((item for item in IDENTITIES if item['id'] == x_demo_identity), None)
        if actor:
            return actor
        error(401, 'invalid_identity', 'Передайте допустимый X-Demo-Identity')
    return require_session(request, token, x_csrf_token)['user']['profile']


def issue_session(connection, request, response, user_id):
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + SESSION_SECONDS
    old = request.cookies.get(COOKIE_NAME)
    if old:
        connection.execute('DELETE FROM sessions WHERE token_hash=?', (digest(old),))
    connection.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
    connection.execute('INSERT INTO sessions VALUES (?,?,?)', (digest(token), user_id, expires_at))
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=os.getenv('COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'},
                        samesite='lax', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'user': account_json(connection, user_id), 'csrf_token': csrf_token(token), 'expires_at': expires_at}


@router.post('/api/auth/register', response_model=SessionResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response):
    check_origin(request)
    rate_limit(request, 'register')
    password_hash = hash_password(payload.password)
    user_id, profile_id = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        with database(write=True) as connection:
            connection.execute('INSERT INTO accounts VALUES (?,?,?,?,?)',
                               (user_id, payload.email, payload.name, password_hash, int(time.time())))
            connection.execute('INSERT INTO profiles VALUES (?,?,?)',
                               (profile_id, payload.role, ProfileFields(name=payload.profile_name).model_dump_json()))
            connection.execute("INSERT INTO memberships VALUES (?,?,'owner')", (user_id, profile_id))
            return issue_session(connection, request, response, user_id)
    except sqlite3.IntegrityError:
        error(409, 'email_taken', 'Этот email уже зарегистрирован')


@router.post('/api/auth/login', response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    check_origin(request)
    rate_limit(request, 'login', payload.email)
    with database() as connection:
        row = connection.execute('SELECT * FROM accounts WHERE email=?', (payload.email,)).fetchone()
    valid = verify_password(payload.password, row['password_hash'] if row else DUMMY_HASH)
    if not row or not valid:
        error(401, 'invalid_credentials', 'Неверный email или пароль')
    with database(write=True) as connection:
        # A password change during derivation must not restore a revoked session.
        latest = connection.execute('SELECT password_hash FROM accounts WHERE id=?', (row['id'],)).fetchone()
        if latest['password_hash'] != row['password_hash']:
            error(401, 'invalid_credentials', 'Неверный email или пароль')
        connection.execute('DELETE FROM auth_attempts WHERE key=?', ('login:email:' + digest(payload.email),))
        return issue_session(connection, request, response, row['id'])


@router.get('/api/auth/session', response_model=SessionResponse)
def session(response: Response, active: dict = Depends(require_session)):
    response.headers['Cache-Control'] = 'no-store'
    return active


@router.post('/api/auth/logout', status_code=204)
def logout(request: Request, response: Response, active: dict = Depends(require_session)):
    with database(write=True) as connection:
        connection.execute('DELETE FROM sessions WHERE token_hash=?', (digest(request.cookies[COOKIE_NAME]),))
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='lax')


@router.post('/api/auth/password', status_code=204)
def change_password(payload: PasswordChange, request: Request, response: Response,
                    active: dict = Depends(require_session)):
    rate_limit(request, 'password', active['user']['id'])
    with database() as connection:
        old = connection.execute('SELECT password_hash FROM accounts WHERE id=?', (active['user']['id'],)).fetchone()[0]
    if not verify_password(payload.current_password, old):
        error(401, 'invalid_credentials', 'Неверный текущий пароль')
    replacement = hash_password(payload.new_password)
    with database(write=True) as connection:
        result = connection.execute('UPDATE accounts SET password_hash=? WHERE id=? AND password_hash=?',
                                    (replacement, active['user']['id'], old))
        if result.rowcount != 1:
            error(409, 'account_changed', 'Пароль уже изменён. Войдите снова.')
        connection.execute('DELETE FROM sessions WHERE user_id=?', (active['user']['id'],))
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='lax')


@router.get('/api/users/me', response_model=AccountResponse)
def me(response: Response, active: dict = Depends(require_session)):
    response.headers['Cache-Control'] = 'no-store'
    return active['user']


@router.patch('/api/users/me', response_model=AccountResponse)
def update_user(payload: UserPatch, response: Response, active: dict = Depends(require_session)):
    with database(write=True) as connection:
        connection.execute('UPDATE accounts SET name=? WHERE id=?', (payload.name, active['user']['id']))
        response.headers['Cache-Control'] = 'no-store'
        return account_json(connection, active['user']['id'])


@router.get('/api/profiles/me', response_model=PublicProfile)
def own_profile(active: dict = Depends(require_session)):
    return active['user']['profile']


@router.patch('/api/profiles/me', response_model=PublicProfile)
def update_profile(payload: ProfilePatch, active: dict = Depends(require_session)):
    profile_id = active['user']['profile']['id']
    with database(write=True) as connection:
        current = connection.execute('SELECT fields FROM profiles WHERE id=?', (profile_id,)).fetchone()
        fields = ProfileFields.model_validate_json(current['fields']).model_dump()
        fields.update(payload.model_dump(exclude_unset=True))
        connection.execute('UPDATE profiles SET fields=? WHERE id=?',
                           (ProfileFields.model_validate(fields).model_dump_json(), profile_id))
        return profile_json(connection, profile_id)


@router.get('/api/profiles/{profile_id}', response_model=PublicProfile)
def public_profile(profile_id: str, actor: dict = Depends(current_identity)):
    with database() as connection:
        # Seeded catalog entries keep readable authors even when demo login is off.
        from .main import IDENTITIES
        demo = next((item for item in IDENTITIES if item['id'] == profile_id), None)
        if demo:
            points = connection.execute('''SELECT COALESCE(SUM(m.points_awarded),0) FROM milestones m
                JOIN proposals p ON p.id=m.proposal_id WHERE p.team_id=? AND m.status='confirmed' ''',
                (profile_id,)).fetchone()[0]
            return {**ProfileFields().model_dump(), **demo, 'members': [], 'team_points': points}
        return profile_json(connection, profile_id)
