from pathlib import Path

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


def test_download_accepts_outputs_prefixed_path(tmp_path, monkeypatch):
    from app import main as main_module

    monkeypatch.setattr(main_module, 'OUTPUT_DIR', tmp_path)
    file_path = tmp_path / 'demo.pptx'
    file_path.write_bytes(b'dummy')

    client = TestClient(app)
    resp = client.get('/v1/download/outputs/demo.pptx')
    assert resp.status_code == 200
    assert resp.content == b'dummy'


def test_home_page_uses_valid_backslash_normalizer():
    client = TestClient(app)
    resp = client.get('/')
    assert resp.status_code == 200
    assert "replace(/\\/g, '/')" in resp.text


def test_home_page_has_non_submitting_form():
    client = TestClient(app)
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'onsubmit="event.preventDefault();"' in resp.text
    assert 'type="button"' in resp.text


def test_home_page_cache_headers():
    client = TestClient(app)
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'no-store' in resp.headers.get('cache-control', '')


def test_chrome_devtools_probe_returns_204():
    client = TestClient(app)
    resp = client.get('/.well-known/appspecific/com.chrome.devtools.json')
    assert resp.status_code == 204
