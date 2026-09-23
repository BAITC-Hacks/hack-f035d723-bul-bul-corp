import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main


class TaskLifecycleTest(unittest.TestCase):
    def test_published_snapshot_survives_edits_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, 'DB_PATH', Path(directory) / 'tasks.sqlite3'):
                with TestClient(main.app) as client:
                    owner = {'X-Demo-Identity': 'business-demo'}
                    team = {'X-Demo-Identity': 'team-alpha'}
                    draft = client.post('/api/tasks', headers=owner, json={'title':'Original', 'context':'Context', 'need':'Need'}).json()
                    url = '/api/tasks/' + draft['id']
                    self.assertEqual(client.get(url, headers=team).status_code, 403)
                    self.assertEqual(client.post(url+'/publish', headers=owner).status_code, 409)
                    self.assertEqual(client.patch(url, headers=team, json={'title':'Wrong'}).status_code, 403)
                    self.assertEqual(client.patch(url, headers=owner, json={'title':None}).status_code, 422)
                    client.post(url+'/confirm', headers=owner)
                    client.post(url+'/publish', headers=owner)
                    published = client.get(url, headers=team).json()
                    edited = client.patch(url, headers=owner, json={'title':'Edited','need':''}).json()
                    self.assertFalse(edited['confirmed'])
                    self.assertEqual(client.get(url, headers=team).json(), published)
                    self.assertEqual(client.get('/api/tasks', headers=team).json()['items'], [published])
                    self.assertEqual(client.post(url+'/publish', headers=owner).status_code, 409)
                    confirmed = client.post(url+'/confirm', headers=owner).json()
                    self.assertLess(confirmed['rating']['total'], published['rating']['total'])
                    self.assertEqual(client.get(url, headers=team).json(), published)
                    client.post(url+'/publish', headers=owner)
                    republished = client.get(url, headers=team).json()
                    self.assertEqual(republished['title'], 'Edited')
                    self.assertEqual(republished['rating'], confirmed['rating'])
                with TestClient(main.app) as restarted:
                    self.assertEqual(restarted.get(url, headers=team).json(), republished)


if __name__ == '__main__':
    unittest.main()
