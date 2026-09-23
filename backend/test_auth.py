import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth, main
from backend.seed import seed


class AccountTests(unittest.TestCase):
    password = 'A-long-test-password!'

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database = patch.object(main, 'DB_PATH', Path(directory.name) / 'accounts.sqlite3')
        database.start()
        self.addCleanup(database.stop)
        environment = patch.dict(os.environ, {
            'DEMO_MODE': 'false', 'COOKIE_SECURE': 'false',
            'AI_API_KEY': '', 'OPENAI_API_KEY': '',
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def new_client(self):
        client = TestClient(main.app)
        self.addCleanup(client.close)
        return client

    def register(self, email='owner@example.com', role='business', client=None):
        client = client or self.client
        response = client.post('/api/auth/register', json={
            'email': email, 'password': self.password, 'name': 'Личный пользователь',
            'role': role, 'profile_name': 'Компания' if role == 'business' else 'Команда',
        })
        self.assertEqual(response.status_code, 201, response.text)
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        return response.json()

    def test_register_login_profile_and_session_persist_without_plain_secrets(self):
        registered = self.register('Owner@Example.com')
        user = registered['user']
        self.assertEqual(user['email'], 'owner@example.com')
        self.assertNotEqual(user['id'], user['profile']['id'])
        token = self.client.cookies.get(auth.COOKIE_NAME)
        with main.db() as connection:
            account = dict(connection.execute('SELECT * FROM accounts').fetchone())
            session = dict(connection.execute('SELECT * FROM sessions').fetchone())
            self.assertNotIn(self.password, json.dumps(account))
            self.assertTrue(auth.verify_password(self.password, account['password_hash']))
            self.assertEqual(session['token_hash'], auth.digest(token))
            self.assertNotIn(token, json.dumps(session))
        with TestClient(main.app) as restarted:
            restarted.cookies.set(auth.COOKIE_NAME, token)
            self.assertEqual(restarted.get('/api/auth/session').json(), registered)
            restarted.cookies.clear()
            logged_in = restarted.post('/api/auth/login', json={'email': 'OWNER@example.com', 'password': self.password})
            self.assertEqual(logged_in.status_code, 200, logged_in.text)
            self.assertEqual(logged_in.json()['user'], user)
            self.assertNotEqual(restarted.cookies.get(auth.COOKIE_NAME), token)
            self.assertIn('HttpOnly', logged_in.headers['set-cookie'])
            self.assertIn('SameSite=lax', logged_in.headers['set-cookie'])
            self.assertEqual(logged_in.headers['cache-control'], 'no-store')

    def test_invalid_credentials_duplicates_and_validation(self):
        self.register()
        stranger = self.new_client()
        for email in ('missing@example.com', 'owner@example.com'):
            response = stranger.post('/api/auth/login', json={'email': email, 'password': 'wrong'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['code'], 'invalid_credentials')
        body = {'email': 'OWNER@example.com', 'password': self.password, 'name': 'Имя',
                'role': 'team', 'profile_name': 'Название'}
        self.assertEqual(stranger.post('/api/auth/register', json=body).status_code, 409)
        for change in ({'password': 'short'}, {'email': 'not-an-email'}, {'role': 'admin'},
                       {'name': ' '}, {'profile_name': ''}, {'id': 'business-demo'}):
            with self.subTest(change=change):
                response = stranger.post('/api/auth/register', json={**body, **change})
                self.assertEqual(response.status_code, 422, response.text)

    def test_concurrent_registration_cannot_duplicate_an_account_or_profile(self):
        clients = [self.new_client(), self.new_client()]
        body = {'email': 'same@example.com', 'password': self.password, 'name': 'Имя',
                'role': 'team', 'profile_name': 'Команда'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda client: client.post('/api/auth/register', json=body).status_code, clients))
        self.assertEqual(sorted(statuses), [201, 409])
        with main.db() as connection:
            for table in ('accounts', 'profiles', 'memberships', 'sessions'):
                self.assertEqual(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 1)

    def test_logout_revokes_only_current_session_and_expiry_is_enforced(self):
        first = self.register()
        first_token = self.client.cookies.get(auth.COOKIE_NAME)
        other_device = self.new_client()
        other_device.post('/api/auth/login', json={'email': first['user']['email'], 'password': self.password})
        response = self.client.post('/api/auth/logout')
        self.assertEqual(response.status_code, 204, response.text)
        self.assertIsNone(self.client.cookies.get(auth.COOKIE_NAME))
        self.client.cookies.set(auth.COOKIE_NAME, first_token)
        self.assertEqual(self.client.get('/api/auth/session').status_code, 401)
        self.assertEqual(other_device.get('/api/auth/session').status_code, 200)
        with main.db(write=True) as connection:
            connection.execute('UPDATE sessions SET expires_at=?', (int(time.time())-1,))
        self.assertEqual(other_device.get('/api/users/me').status_code, 401)

    def test_csrf_origin_cookie_security_and_cors(self):
        self.register()
        csrf = self.client.headers.pop('X-CSRF-Token')
        self.assertEqual(self.client.post('/api/tasks', json={}).status_code, 403)
        self.client.headers['X-CSRF-Token'] = 'wrong'
        self.assertEqual(self.client.patch('/api/profiles/me', json={'name': 'Wrong'}).status_code, 403)
        self.client.headers['X-CSRF-Token'] = csrf
        response = self.client.post('/api/tasks', json={}, headers={'Origin': 'https://attacker.invalid'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'invalid_origin')
        anonymous = self.new_client()
        response = anonymous.post('/api/auth/login', json={'email': 'owner@example.com', 'password': self.password},
                                  headers={'Origin': 'https://attacker.invalid'})
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/api/tasks', json={}, headers={'Origin': 'http://localhost:5173'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
        self.assertEqual(response.headers['access-control-allow-credentials'], 'true')
        preflight = self.client.options('/api/tasks', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type,x-csrf-token',
        })
        self.assertEqual(preflight.status_code, 200)
        with patch.dict(os.environ, {'COOKIE_SECURE': 'true'}):
            response = anonymous.post('/api/auth/login', json={'email': 'owner@example.com', 'password': self.password})
            self.assertIn('Secure', response.headers['set-cookie'])

    def test_demo_header_cannot_impersonate_registered_user(self):
        anonymous = self.new_client()
        self.assertEqual(anonymous.get('/api/demo-identities').status_code, 404)
        self.assertEqual(anonymous.get('/api/tasks', headers={'X-Demo-Identity': 'business-demo'}).status_code, 401)
        registered = self.register()
        with patch.dict(os.environ, {'DEMO_MODE': 'true'}):
            demo_task = anonymous.post('/api/tasks', headers={'X-Demo-Identity': 'business-demo'}, json={}).json()
            denied = self.client.patch('/api/tasks/'+demo_task['id'], headers={'X-Demo-Identity': 'business-demo'}, json={'title': 'Hijack'})
            self.assertEqual(denied.status_code, 403)
            real_task = self.client.post('/api/tasks', headers={'X-Demo-Identity': 'business-demo'}, json={}).json()
            self.assertEqual(real_task['owner_id'], registered['user']['profile']['id'])
            self.client.cookies.clear()
            self.client.cookies.set(auth.COOKIE_NAME, 'x'*43)
            self.assertEqual(self.client.get('/api/tasks', headers={'X-Demo-Identity': 'business-demo'}).status_code, 401)

    def test_public_profile_excludes_email_and_protected_fields_cannot_be_edited(self):
        session = self.register(role='team')
        profile_id = session['user']['profile']['id']
        updated = self.client.patch('/api/profiles/me', json={
            'description': 'Команда анализа данных', 'skills': ['Python'], 'interests': ['Образование'],
            'technologies': ['SQLite'], 'portfolio_urls': ['https://example.com/work'],
            'contact': 'Публичный контакт по желанию',
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        reader = self.new_client()
        self.register('reader@example.com', client=reader)
        public = reader.get('/api/profiles/'+profile_id)
        self.assertEqual(public.status_code, 200, public.text)
        self.assertNotIn(session['user']['email'], public.text)
        self.assertNotIn('password', public.text)
        self.assertEqual(public.json()['skills'], ['Python'])
        for change in ({'id': 'business-demo'}, {'role': 'business'}, {'team_points': 999},
                       {'members': []}, {'team_id': 'team-alpha'}, {'email': 'another@example.com'},
                       {'website': 'javascript:alert(1)'}, {'skills': [' ']}, {'name': None}):
            with self.subTest(change=change):
                self.assertEqual(self.client.patch('/api/profiles/me', json=change).status_code, 422)
        self.assertEqual(reader.patch('/api/profiles/'+profile_id, json={'name': 'Hijack'}).status_code, 405)
        renamed = self.client.patch('/api/users/me', json={'name': 'Новое имя'})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(reader.get('/api/profiles/'+profile_id).json()['members'][0]['name'], 'Новое имя')
        self.assertEqual(self.client.get('/api/profiles/me').json()['team_points'], 0)

    def test_password_change_revokes_every_session_and_old_password(self):
        self.register()
        second = self.new_client()
        second.post('/api/auth/login', json={'email': 'owner@example.com', 'password': self.password})
        wrong = self.client.post('/api/auth/password', json={'current_password': 'wrong', 'new_password': 'New-long-password!'})
        self.assertEqual(wrong.status_code, 401)
        changed = self.client.post('/api/auth/password', json={'current_password': self.password, 'new_password': 'New-long-password!'})
        self.assertEqual(changed.status_code, 204, changed.text)
        self.assertEqual(second.get('/api/auth/session').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/session').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'owner@example.com', 'password': self.password}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'New-long-password!'}).status_code, 200)

    def test_seed_authors_remain_readable_without_enabling_demo_impersonation(self):
        seed()
        self.register(role='team')
        catalog = self.client.get('/api/tasks').json()['items']
        self.assertEqual(len(catalog), 5)
        for task in catalog:
            author = self.client.get('/api/profiles/'+task['owner_id'])
            self.assertEqual(author.status_code, 200, author.text)
            self.assertEqual(author.json()['role'], 'business')
        self.assertEqual(self.client.get('/api/profiles/team-alpha').status_code, 200)
        self.assertEqual(self.client.get('/api/demo-identities').status_code, 404)
        anonymous = self.new_client()
        self.assertEqual(anonymous.get('/api/tasks', headers={'X-Demo-Identity': 'business-demo'}).status_code, 401)

    def test_login_throttle_is_persistent_and_expires(self):
        body = {'email': 'unknown@example.com', 'password': 'wrong'}
        # Exercise the real limiter while avoiding ten expensive dummy derivations.
        with patch.object(auth, 'verify_password', return_value=False):
            for _ in range(10):
                self.assertEqual(self.client.post('/api/auth/login', json=body).status_code, 401)
            with TestClient(main.app) as restarted:
                limited = restarted.post('/api/auth/login', json=body)
                self.assertEqual(limited.status_code, 429)
                self.assertGreater(int(limited.headers['retry-after']), 0)
            with main.db(write=True) as connection:
                connection.execute('UPDATE auth_attempts SET expires_at=?', (int(time.time())-1,))
            self.assertEqual(self.client.post('/api/auth/login', json=body).status_code, 401)

    def test_real_accounts_enforce_ownership_through_entire_workflow(self):
        owner = self.register()
        other_business = self.new_client()
        self.register('other@example.com', client=other_business)
        team = self.new_client()
        team_session = self.register('team@example.com', role='team', client=team)
        rival = self.new_client()
        self.register('rival@example.com', role='team', client=rival)
        task = self.client.post('/api/tasks', json={'need': 'Нужно распределять обращения'}).json()
        url = '/api/tasks/'+task['id']
        self.assertEqual(task['owner_id'], owner['user']['profile']['id'])
        for intruder in (other_business, team, rival):
            self.assertEqual(intruder.get(url).status_code, 403)
            self.assertEqual(intruder.patch(url, json={'title': 'Hijack'}).status_code, 403)
            for suffix, body in (('/questions', None), ('/compose', {'answers': []}), ('/confirm', None), ('/publish', None)):
                self.assertEqual(intruder.post(url+suffix, json=body).status_code, 403)
        self.client.post(url+'/confirm')
        self.client.post(url+'/publish')
        proposal_body = {'idea': 'Маршрутизация', 'plan': 'Импорт и проверка', 'duration': '7 дней'}
        self.assertEqual(self.client.post(url+'/proposals', json=proposal_body).status_code, 403)
        self.assertEqual(team.post('/api/tasks', json={}).status_code, 403)
        proposal = team.post(url+'/proposals', json=proposal_body).json()
        self.assertEqual(proposal['team_id'], team_session['user']['profile']['id'])
        decision = '/api/proposals/'+proposal['id']+'/decision'
        for intruder in (other_business, team, rival):
            self.assertEqual(intruder.post(decision, json={'decision': 'selected'}).status_code, 403)
        self.assertEqual(self.client.post(decision, json={'decision': 'selected'}).status_code, 200)
        milestone = '/api/proposals/'+proposal['id']+'/milestone'
        result = {'description': 'Прототип', 'result_url': 'https://example.com/result'}
        self.assertEqual(rival.post(milestone, json=result).status_code, 403)
        stage = team.post(milestone, json=result).json()
        review = '/api/milestones/'+stage['id']+'/review'
        for intruder in (other_business, team, rival):
            self.assertEqual(intruder.post(review, json={'decision': 'confirmed'}).status_code, 403)
        for _ in range(2):
            self.assertEqual(self.client.post(review, json={'decision': 'confirmed'}).status_code, 200)
        self.assertEqual(team.get('/api/team/proposals').json()['team_points'], 10)
        self.assertEqual(team.get('/api/profiles/me').json()['team_points'], 10)
        self.assertEqual(rival.get('/api/team/proposals').json()['items'], [])


if __name__ == '__main__':
    unittest.main()
