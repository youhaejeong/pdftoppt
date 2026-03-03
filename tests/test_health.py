from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'



def test_home_page_has_file_input():
    client = TestClient(app)
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'type="file"' in resp.text

