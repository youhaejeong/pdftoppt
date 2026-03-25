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


def test_home_page_slide_count_range():
    client = TestClient(app)
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'name="slide_count"' in resp.text
    assert 'min="10"' in resp.text
    assert 'max="50"' in resp.text


def test_process_rejects_too_small_slide_count():
    client = TestClient(app)
    files = {"pdf_file": ("sample.pdf", b"%PDF-1.4 test", "application/pdf")}
    data = {
        "purpose": "내부 공유",
        "audience": "팀 리더",
        "tone": "공식적",
        "slide_count": "9",
    }
    resp = client.post('/v1/process', files=files, data=data)
    assert resp.status_code == 400
    assert 'slide_count는 10 이상 50 이하만 가능합니다.' in resp.text


def test_process_rejects_too_large_slide_count():
    client = TestClient(app)
    files = {"pdf_file": ("sample.pdf", b"%PDF-1.4 test", "application/pdf")}
    data = {
        "purpose": "내부 공유",
        "audience": "팀 리더",
        "tone": "공식적",
        "slide_count": "51",
    }
    resp = client.post('/v1/process', files=files, data=data)
    assert resp.status_code == 400
    assert 'slide_count는 10 이상 50 이하만 가능합니다.' in resp.text
