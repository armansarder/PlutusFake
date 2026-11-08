"""Run from the repo root:  python -m pytest tests/ -v"""
import json
from datetime import date

import pytest

from calculation_engine.history import RawDirHistorySource, build_history

CUSTOMER = json.load(open('pipeline/data/seed_ids.json'))['customer_id']
TOKEN = 'test-token-' + 'x' * 40
TODAY = date(2026, 11, 8)


@pytest.fixture
def source():
    return RawDirHistorySource('pipeline/data/raw', customer_id=CUSTOMER)


def test_monthly_totals_match_frontend(source):
    months = {m['month']: m for m in build_history(source, today=TODAY, months_back=12)['months']}
    assert months['2026-08']['spending'] == '2910.00'
    assert months['2026-09']['spending'] == '2620.00'
    assert months['2026-10']['spending'] == '2550.00'
    assert months['2026-11']['spending'] == '490.00'
    assert months['2026-06']['income'] == '3350.00'   # includes the one-time bonus
    assert months['2026-10']['income'] == '3200.00'


def test_categories_use_frontend_ids(source):
    october = {m['month']: m for m in build_history(source, today=TODAY)['months']}['2026-10']
    totals = {c['category']: c['amount'] for c in october['by_category']}
    assert totals == {'housing': '1150.00', 'groceries': '380.00', 'transport': '210.00',
                      'utilities': '170.00', 'fun': '180.00', 'subscriptions': '70.00',
                      'other': '390.00'}


def test_transfers_are_savings_not_spending(source):
    rows = build_history(source, today=TODAY)['transactions']
    transfers = [t for t in rows if t['is_transfer']]
    assert transfers
    assert all(t['category'] == 'savings' for t in transfers)
    assert not any(t['is_spending'] or t['is_income'] for t in transfers)


def test_month_filter_for_bar_click(source):
    result = build_history(source, month='2026-10', today=TODAY)
    assert result['selected_month'] == '2026-10'
    assert result['transactions'] and all(t['date'].startswith('2026-10') for t in result['transactions'])


def test_future_dated_rows_are_excluded(source):
    result = build_history(source, today=date(2026, 10, 15))
    assert all(t['date'] <= '2026-10-15' for t in result['transactions'])


def test_wrong_customer_is_rejected():
    with pytest.raises(ValueError):
        build_history(RawDirHistorySource('pipeline/data/raw', customer_id='someone-else'))


def test_history_endpoint_requires_auth_and_returns_data(source):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from calculation_engine.data_loader import JsonFileAdapter
    from calculation_engine.main import create_app
    from calculation_engine.security import SecuritySettings

    app = create_app(source=JsonFileAdapter('unused.json'),
                     settings=SecuritySettings(api_token=TOKEN, customer_id=CUSTOMER),
                     history_source=source)
    client = TestClient(app)
    assert client.get('/api/history').status_code == 401
    auth = {'Authorization': f'Bearer {TOKEN}'}
    response = client.get('/api/history?months=6', headers=auth)
    assert response.status_code == 200
    assert response.json()['data']['customer_id'] == CUSTOMER
    assert client.get('/api/history?month=2026-13', headers=auth).status_code == 422
