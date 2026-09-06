import os
import urllib.parse

import pytest

os.environ.setdefault(
    "DATABASE_URL", "postgresql://guestbook:devpass@127.0.0.1:5433/guestbook"
)
os.environ["IP_HASH_SALT"] = "test-salt"

# 아래 client fixture가 매번 테이블을 DROP한다. DATABASE_URL이 실수로 Neon을
# 가리킨 채로 pytest를 돌리면 방명록이 통째로 날아간다. local이 아니면 멈춘다.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}
_host = urllib.parse.urlsplit(os.environ["DATABASE_URL"]).hostname or ""
if _host not in _LOCAL_HOSTS:
    raise SystemExit(
        f"테스트는 local DB에서만 돌린다. DATABASE_URL이 '{_host}'를 가리키고 있다.\n"
        "테이블을 DROP하는 fixture라 원격 DB에 붙으면 데이터가 사라진다."
    )

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
