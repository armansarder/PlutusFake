"""Pipeline checks for the demo customer. Run from the repo root:  python -m pytest tests/ -v"""
import json
import subprocess
import sys

import pytest

AS_OF = '2026-11-08'


@pytest.fixture(scope='module')
def outputs():
    subprocess.run([sys.executable, 'pipeline/transform.py', '--as-of', AS_OF],
                   check=True, capture_output=True)
    read = lambda path: json.load(open(path))
    return {
        'summary': read('pipeline/data/clean/monthly_summary.json'),
        'patterns': read('pipeline/data/clean/recurring.json'),
        'transactions': read('pipeline/data/clean/transactions.json'),
        'upcoming': read('calculation_engine/private_data/upcoming.json'),
    }


def test_paydays_are_the_14th_and_28th(outputs):
    pay = [e['date'] for e in outputs['upcoming']['upcoming_transactions'] if e['type'] == 'income']
    assert pay[:3] == ['2026-11-14', '2026-11-28', '2026-12-14']


def test_bonus_is_one_time_not_projected(outputs):
    one_time = [t for t in outputs['transactions'] if t['spend_type'] == 'one_time']
    assert [t['description'] for t in one_time] == ['Performance bonus']
    assert all('bonus' not in e['description'].lower()
               for e in outputs['upcoming']['upcoming_transactions'])


def test_subscriptions_survive_price_changes(outputs):
    subs = {p['name']: p for p in outputs['patterns'] if p['kind'] == 'subscription'}
    assert set(subs) == {'iCloud', 'Spotify', 'Netflix', 'Planet Fitness'}
    assert subs['Spotify']['amount'] == -17.0 and subs['Spotify']['price_changes']


def test_everyday_spending_excludes_scheduled_items(outputs):
    for t in outputs['transactions']:
        if t['spend_type'] == 'everyday':
            assert t['source'] in ('purchase', 'withdrawal')
            assert t['category'] not in ('subscriptions', 'housing', 'utilities')


def test_savings_tracked(outputs):
    assert sum(m['saved'] for m in outputs['summary'].values()) == 800


def test_schedule_passes_engine_contract(outputs):
    from calculation_engine.models import FinancialData
    data = FinancialData.model_validate(outputs['upcoming'])
    assert str(data.as_of_date) == AS_OF
