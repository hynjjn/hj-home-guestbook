import os

import pytest

os.environ.setdefault(
    "DATABASE_URL", "postgresql://guestbook:devpass@127.0.0.1:5433/guestbook"
)
os.environ["IP_HASH_SALT"] = "test-salt"

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    # 테이블을 지우고 다시 만든다. id가 1부터 다시 시작해야 커서 페이지네이션
    # 테스트가 앞 테스트의 잔여 행에 걸리지 않는다.
    with db.cursor() as conn:
        conn.execute("DROP TABLE IF EXISTS entries, photos")
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
