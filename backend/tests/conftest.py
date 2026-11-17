import os
import sys
import tempfile
from pathlib import Path

# Isolated temp data dir and no AI key, set BEFORE the app is imported.
_tmp = tempfile.mkdtemp(prefix="healthmate_test_")
os.environ["DATA_DIR"] = _tmp
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["GEMINI_API_KEY"] = ""
os.environ["SEED_DEMO"] = "true"
os.environ["JWT_SECRET"] = "test-secret-for-pytest-only-0123456789"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _register(client, email, name="Test User", password="Passw0rd!", age=30):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password, "age": age})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture()
def auth(client):
    import uuid
    return _register(client, f"u{uuid.uuid4().hex[:8]}@example.com")


@pytest.fixture()
def register():
    return _register
