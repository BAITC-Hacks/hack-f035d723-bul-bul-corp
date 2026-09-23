import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main
from backend.schemas import TaskFields


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

    def test_answer_to_offered_clarification_survives_confirmation_and_publication(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(main, 'DB_PATH', Path(directory) / 'tasks.sqlite3'), \
                patch.dict(os.environ, {'AI_API_KEY':'', 'OPENAI_API_KEY':''}):
            with TestClient(main.app) as client:
                owner = {'X-Demo-Identity':'business-demo'}
                team = {'X-Demo-Identity':'team-alpha'}
                fields = {name:'Исходные сведения' for name in TaskFields.model_fields}
                fields['title'] = 'Распределение обращений'
                fields.update(success_criteria='Точность 90%', contact='demo@example.com',
                              consultation='Еженедельный созвон')
                draft = client.post('/api/tasks',headers=owner,json=fields).json()
                url = '/api/tasks/'+draft['id']
                client.post(url+'/confirm',headers=owner)
                client.post(url+'/publish',headers=owner)
                published = client.get(url,headers=team).json()
                question = client.post(url+'/questions',headers=owner).json()['questions'][0]
                clarification = 'В названии важно выделить обращения юридических лиц.'
                body = {'answers':[{'question':question,'answer':clarification}]}
                result = client.post(url+'/compose',headers=owner,json=body)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['title'], fields['title']+'\n'+clarification)
                self.assertFalse(result.json()['confirmed'])
                self.assertEqual(client.get(url,headers=team).json(),published)
                self.assertEqual(client.post(url+'/publish',headers=owner).status_code,409)
                retried = client.post(url+'/compose',headers=owner,json=body).json()
                self.assertEqual(retried['title'],result.json()['title'])
                client.post(url+'/confirm',headers=owner)
                self.assertEqual(client.get(url,headers=team).json(),published)
                client.post(url+'/publish',headers=owner)
                self.assertEqual(client.get(url,headers=team).json()['title'],result.json()['title'])

    def test_unknown_card_gains_points_only_after_facts_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(main, 'DB_PATH', Path(directory) / 'tasks.sqlite3'):
            with TestClient(main.app) as client:
                owner = {'X-Demo-Identity': 'business-demo'}
                draft = client.post('/api/tasks', headers=owner, json={
                    name: 'Пока неизвестно, требуется уточнение' for name in TaskFields.model_fields
                }).json()
                url = '/api/tasks/' + draft['id']
                confirmed = client.post(url+'/confirm', headers=owner).json()
                self.assertTrue(confirmed['confirmed'])
                self.assertEqual(confirmed['rating']['total'], 0)
                self.assertEqual(len(confirmed['rating']['missing']), 7)
                edited = client.patch(url, headers=owner, json={
                    'context': 'Обращения теряются при ручной передаче между отделами',
                    'need': 'Автоматически направлять обращения ответственному отделу',
                    'users': 'Операторы поддержки',
                }).json()
                self.assertFalse(edited['confirmed'])
                self.assertEqual(edited['rating']['total'], 0)
                confirmed = client.post(url+'/confirm', headers=owner).json()
                self.assertEqual(confirmed['rating']['total'], 30)
                self.assertEqual(
                    {c['key']: c['points'] for c in confirmed['rating']['categories'] if c['points']},
                    {'context_need': 20, 'users': 10},
                )

    def test_unknown_facts_questions_answers_and_confirmation_raise_rating(self):
        facts = {
            'data_materials': 'Синтетические обращения в CSV',
            'users': 'Операторы поддержки',
            'expected_result': 'Прототип маршрутизации',
            'context': 'Обращения теряются при передаче между отделами',
            'need': 'Направлять обращения ответственным операторам',
            'constraints': 'Без передачи персональных данных наружу',
        }
        answer_map = {main.ai.FIELD_QUESTIONS[name]: value for name, value in facts.items()}
        fields = {name: 'Не знаю' for name in TaskFields.model_fields}
        fields.update(title='Маршрутизация', topic='Поддержка',
                      success_criteria='Снизить дефицит на 20%', contact='demo@example.com',
                      consultation='Еженедельный созвон')
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(main, 'DB_PATH', Path(directory) / 'tasks.sqlite3'), \
                patch.dict(os.environ, {'AI_API_KEY': '', 'OPENAI_API_KEY': ''}):
            with TestClient(main.app) as client:
                owner = {'X-Demo-Identity': 'business-demo'}
                task = client.post('/api/tasks', headers=owner, json=fields).json()
                url = '/api/tasks/' + task['id']
                confirmed = client.post(url+'/confirm', headers=owner).json()
                previous = confirmed['rating']['total']
                self.assertEqual(previous, 25)
                for _ in range(2):
                    questions = client.post(url+'/questions', headers=owner).json()['questions']
                    self.assertTrue(3 <= len(questions) <= 5)
                    self.assertTrue(all(main.ai.QUESTION_FIELDS[main.ai._normalize(q)] in facts for q in questions))
                    answers = [{'question': q, 'answer': answer_map[q]} for q in questions if q in answer_map]
                    composed = client.post(url+'/compose', headers=owner, json={'answers': answers}).json()
                    self.assertFalse(composed['confirmed'])
                    self.assertFalse(composed['published'])
                    self.assertEqual(composed['rating']['total'], 0)
                    confirmed = client.post(url+'/confirm', headers=owner).json()
                    self.assertGreater(confirmed['rating']['total'], previous)
                    previous = confirmed['rating']['total']
                self.assertEqual(previous, 100)
                for name, fact in facts.items():
                    self.assertEqual(confirmed[name], 'Не знаю\n' + fact)


if __name__ == '__main__':
    unittest.main()
