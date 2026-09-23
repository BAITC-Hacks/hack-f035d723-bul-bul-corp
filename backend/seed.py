"""Load synthetic data without overwriting user-created tasks."""
import argparse
import json

from . import main
from .rating import calculate_rating
from .schemas import ProposalCreate, TaskFields


def seed(reset: bool = False) -> dict[str, int]:
    data = json.loads((main.ROOT / 'fixtures/demo-data.json').read_text(encoding='utf-8'))
    tasks = data['drafts'] + data['cards']
    identities = {item['id']: item for item in main.IDENTITIES}
    for item in tasks:
        TaskFields.model_validate(item['fields'])
        if identities[item['owner_id']]['role'] != 'business':
            raise ValueError('Fixture owner must be a business')
    for item in data['proposals']:
        ProposalCreate.model_validate({key: item[key] for key in ('idea', 'plan', 'duration', 'prototype_url')})
        if identities[item['team_id']]['role'] != 'team' or item['status'] != 'pending':
            raise ValueError('Fixture proposal must be pending and owned by a team')
    main.init_db()
    inserted = {'drafts':0, 'cards':0, 'proposals':0}
    with main.db(write=True) as connection:
        if reset:
            for item in tasks:
                connection.execute('DELETE FROM milestones WHERE proposal_id IN (SELECT id FROM proposals WHERE task_id=?)', (item['id'],))
                connection.execute('DELETE FROM proposals WHERE task_id=?', (item['id'],))
                connection.execute('DELETE FROM tasks WHERE id=?', (item['id'],))
        for group in ('drafts', 'cards'):
            published = group == 'cards'
            for item in data[group]:
                fields = TaskFields.model_validate(item['fields'])
                rating = calculate_rating(fields, published).model_dump_json()
                timestamp = main.now()
                result = connection.execute(
                    'INSERT OR IGNORE INTO tasks (id,owner_id,fields,published_fields,published_rating,confirmed,published,version,rating,created_at,updated_at,published_version,published_updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (item['id'], item['owner_id'], fields.model_dump_json(), fields.model_dump_json() if published else '{}', rating if published else None,
                     int(published), int(published), 1, rating, timestamp, timestamp, 1 if published else None, timestamp if published else None),
                )
                inserted[group] += result.rowcount
        for item in data['proposals']:
            result = connection.execute('INSERT OR IGNORE INTO proposals (id,task_id,team_id,idea,plan,duration,prototype_url,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                tuple(item[key] for key in ('id','task_id','team_id','idea','plan','duration','prototype_url','status')) + (main.now(),))
            inserted['proposals'] += result.rowcount
    return inserted


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Load AI Sana demo data. No changes to existing records unless --reset.')
    parser.add_argument('--reset', action='store_true', help='Replace fixture tasks and ALL proposals/milestones linked to those demo tasks; preserve other tasks.')
    args = parser.parse_args()
    print(json.dumps(seed(reset=args.reset)))
