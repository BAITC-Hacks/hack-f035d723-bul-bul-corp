import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.seed import seed


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = patch.object(main, 'DB_PATH', Path(self.directory.name) / 'test.sqlite3')
        self.database.start()
        self.addCleanup(self.database.stop)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.business = {'X-Demo-Identity':'business-demo'}
        self.other = {'X-Demo-Identity':'business-second'}
        self.team = {'X-Demo-Identity':'team-alpha'}
        self.beta = {'X-Demo-Identity':'team-beta'}

    def post(self, path, body=None, actor=None, status=200):
        response = self.client.post('/api'+path, headers=actor or self.business, json=body)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def task(self):
        task = self.post('/tasks', {'title':'Audit', 'topic':'IT'})
        url = '/tasks/'+task['id']
        self.post(url+'/confirm')
        self.post(url+'/publish')
        return task['id']

    def proposal(self, task_id, actor=None):
        return self.post('/tasks/'+task_id+'/proposals', {'idea':'CSV import','plan':'Import and review','duration':'7 days','prototype_url':'https://example.com/demo'}, actor or self.team)

    def selected(self):
        proposal = self.proposal(self.task())
        self.post('/proposals/'+proposal['id']+'/decision', {'decision':'selected'})
        return proposal['id']

    def test_milestone_resubmission_permissions_and_terminal_state(self):
        proposal_id = self.selected()
        url = '/proposals/'+proposal_id+'/milestone'
        body = {'description':'Prototype','result_url':'https://example.com/result'}
        self.post(url, body, self.beta, 403)
        self.post(url, {'description':'Prototype'}, self.team, 422)
        first = self.post(url, body, self.team)
        review = '/milestones/'+first['id']+'/review'
        self.post(review, {'decision':'confirmed'}, self.team, 403)
        self.post(review, {'decision':'confirmed'}, self.other, 403)
        self.post(review, {'decision':'changes_requested'}, status=422)
        self.post(review, {'decision':'changes_requested','comment':'Add acceptance evidence'})
        self.post(review, {'decision':'confirmed'}, status=409)
        revised = self.post(url, {**body, 'description':'Prototype with evidence'}, self.team)
        self.assertEqual(first['id'], revised['id'])
        self.assertEqual(revised['status'], 'submitted')
        self.assertEqual(revised['points_awarded'], 0)
        self.post('/proposals/'+proposal_id+'/decision', {'decision':'rejected'}, status=409)
        confirmed = self.post(review, {'decision':'confirmed'})
        repeated = self.post(review, {'decision':'confirmed'})
        self.assertEqual(confirmed, repeated)
        self.post(review, {'decision':'changes_requested','comment':'Reopen'}, status=409)
        self.post(url, {**body, 'description':'Another stage'}, self.team, 409)
        own = self.client.get('/api/team/proposals', headers=self.team).json()
        self.assertEqual(own['team_points'], 10)
        self.assertEqual(own['items'][0]['milestone']['status'], 'confirmed')
        # Real API reads after a fresh lifespan on the same file.
        with TestClient(main.app) as restarted:
            restored = restarted.get('/api/team/proposals', headers=self.team).json()
            self.assertEqual(restored, own)

    def test_concurrent_submissions_and_confirmations_award_once(self):
        proposal_id = self.selected()
        def submit(_):
            return self.client.post('/api/proposals/'+proposal_id+'/milestone', headers=self.team,
                                    json={'description':'Prototype','result_url':'https://example.com/result'})
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(submit, range(8)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len({response.json()['id'] for response in responses}), 1)
        mid = responses[0].json()['id']
        def review(_):
            return self.client.post('/api/milestones/'+mid+'/review', headers=self.business, json={'decision':'confirmed'})
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(review, range(8)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        own = self.client.get('/api/team/proposals', headers=self.team).json()
        self.assertEqual(own['team_points'], 10)

    def test_open_catalog_low_score_multiple_teams_and_validation(self):
        task_id = self.task()
        items = self.client.get('/api/tasks?topic=it&level=draft', headers=self.beta).json()['items']
        self.assertEqual([item['id'] for item in items], [task_id])
        self.assertEqual(items[0]['rating']['total'], 0)
        one = self.proposal(task_id)
        two = self.proposal(task_id, self.beta)
        self.post('/proposals/'+one['id']+'/decision', {'decision':'selected'})
        listing = self.client.get('/api/tasks/'+task_id+'/proposals', headers=self.business).json()['items']
        self.assertEqual(next(item for item in listing if item['id']==two['id'])['status'], 'pending')
        self.post('/proposals/'+two['id']+'/decision', {'decision':'selected'})
        self.post('/proposals/'+one['id']+'/decision', {'decision':'rejected'}, self.other, 403)
        for body in ({'idea':' ','plan':' ','duration':' '}, {'idea':'X','plan':'X','duration':'1d','prototype_url':'javascript:alert(1)'}):
            self.post('/tasks/'+task_id+'/proposals', body, self.team, 422)
        self.post('/tasks', {'description':'Must not silently disappear'}, status=422)
        self.assertEqual(self.client.get('/api/tasks?level=invalid',headers=self.team).status_code, 422)
        missing = self.client.get('/api/unknown')
        self.assertEqual(missing.status_code, 404)
        self.assertIn('code', missing.json())
        self.assertEqual(self.client.get('/api/tasks').status_code, 401)

    def test_seed_idempotency_and_reset_preserves_user_tasks(self):
        user_task = self.post('/tasks', {'title':'User task'})
        self.assertEqual(seed(), {'drafts':5, 'cards':5, 'proposals':5})
        self.assertEqual(seed(), {'drafts':0, 'cards':0, 'proposals':0})
        self.assertEqual(seed(reset=True), {'drafts':5, 'cards':5, 'proposals':5})
        user = self.client.get('/api/tasks/'+user_task['id'],headers=self.business)
        self.assertEqual(user.json()['title'], 'User task')
        catalog = self.client.get('/api/tasks',headers=self.team).json()['items']
        self.assertEqual(len(catalog),5)
        totals = [item['rating']['total'] for item in catalog]
        self.assertEqual(totals,sorted(totals,reverse=True))
        identities = self.client.get('/api/demo-identities').json()
        teams = [identity for identity in identities if identity['role']=='team']
        self.assertEqual(len(teams),5)
        self.assertTrue(all(team['interests'] and team['skills'] and team['technologies'] for team in teams))

    def test_legacy_duplicate_milestones_archived_without_double_points(self):
        proposal_id = self.selected()
        with main.db(write=True) as connection:
            connection.execute('DROP INDEX one_milestone_per_proposal')
            for i in range(2):
                connection.execute('INSERT INTO milestones VALUES (?,?,?,?,?,?,?)',
                                   ('legacy-'+str(i),proposal_id,'Result','https://example.com','confirmed','',10))
        main.init_db()
        own = self.client.get('/api/team/proposals',headers=self.team).json()
        self.assertEqual(own['team_points'],10)
        with main.db() as connection:
            archived = [json.loads(row['record']) for row in connection.execute('SELECT record FROM milestone_legacy_archive')]
        self.assertEqual({row['id'] for row in archived},{'legacy-0','legacy-1'})
        main.init_db()
        self.assertEqual(self.client.get('/api/team/proposals',headers=self.team).json()['team_points'],10)


if __name__ == '__main__':
    unittest.main()
