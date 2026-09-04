import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="guestbook-test-"))
os.environ["DB_PATH"] = str(_tmp / "guestbook.db")
os.environ["MEDIA_DIR"] = str(_tmp / "media")
os.environ["IP_HASH_SALT"] = "test-salt"

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    db.init()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_entry(client):
    def _make(name="은지", content="다녀갑니다", pin="1234", photo=None):
        files = {"photo": photo} if photo else None
        r = client.post(
            "/api/entries",
            data={"name": name, "content": content, "pin": pin},
            files=files,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
