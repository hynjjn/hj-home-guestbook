import importlib
import io
from unittest import mock

from PIL import Image

from app import config, security


def photo_bytes(*, with_gps=True) -> bytes:
    img = Image.new("RGB", (2400, 1200), (120, 180, 220))
    buf = io.BytesIO()
    if with_gps:
        exif = img.getexif()
        exif[0x8825] = {1: "N", 2: (37.0, 30.0, 0.0)}  # GPSInfo
        exif[0x010F] = "TestCam"
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


# ---------- 목록, 작성 ----------


def test_empty_feed(client):
    body = client.get("/api/entries").json()
    assert body == {"entries": [], "total": 0, "has_more": False}


def test_create_and_list(client, make_entry):
    made = make_entry(name="tuna", content="김치찜 맛있었어요")
    body = client.get("/api/entries").json()

    assert body["total"] == 1
    assert body["has_more"] is False
    entry = body["entries"][0]
    assert entry["id"] == made["id"]
    assert entry["name"] == "tuna"
    assert entry["content"] == "김치찜 맛있었어요"
    assert entry["photo"] is None
    assert entry["reply"] is None
    assert entry["mine"] is False


def test_edit_token_never_leaks(client, make_entry):
    """조회 API 어디에도 edit_token이 나오면 안 된다"""
    made = make_entry()
    r = client.get("/api/entries")
    assert "edit_token" not in r.text
    assert made["edit_token"] not in r.text


def test_mine_flag(client, make_entry):
    made = make_entry()
    r = client.get("/api/entries", headers={"X-Edit-Tokens": f"deadbeef,{made['edit_token']}"})
    assert r.json()["entries"][0]["mine"] is True


def test_cursor_pagination(client, make_entry):
    ids = [make_entry(content=f"글 {i}")["id"] for i in range(5)]

    first = client.get("/api/entries", params={"limit": 2}).json()
    assert [e["id"] for e in first["entries"]] == ids[:-3:-1]
    assert first["has_more"] is True

    second = client.get(
        "/api/entries", params={"limit": 2, "before": first["entries"][-1]["id"]}
    ).json()
    assert [e["id"] for e in second["entries"]] == [ids[2], ids[1]]


def test_validation(client):
    def post(**over):
        payload = {"name": "은지", "content": "안녕", "pin": "1234"} | over
        return client.post("/api/entries", data=payload)

    assert post(name="   ").status_code == 422
    assert post(name="열두자를넘기는아주긴이름입니다").status_code == 422
    assert post(content="").status_code == 422
    assert post(content="가" * 1001).status_code == 422
    assert post(pin="12a4").status_code == 422
    assert post(pin="12345").status_code == 422


# ---------- 수정, 삭제 ----------


def test_patch_with_permanent_token(client, make_entry):
    made = make_entry(content="원문")
    r = client.patch(
        f"/api/entries/{made['id']}",
        json={"content": "고친 내용"},
        headers={"X-Edit-Token": made["edit_token"]},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "고친 내용"
    assert r.json()["updated_at"] is not None


def test_patch_rejects_bad_token(client, make_entry):
    made = make_entry()
    r = client.patch(
        f"/api/entries/{made['id']}",
        json={"content": "몰래 수정"},
        headers={"X-Edit-Token": "0" * 64},
    )
    assert r.status_code == 401


def test_deleted_entries_hidden(client, make_entry):
    """soft delete된 글은 목록에 없다"""
    made = make_entry()
    kept = make_entry(content="남는 글")

    r = client.delete(
        f"/api/entries/{made['id']}", headers={"X-Edit-Token": made["edit_token"]}
    )
    assert r.status_code == 204

    body = client.get("/api/entries").json()
    assert [e["id"] for e in body["entries"]] == [kept["id"]]
    assert body["total"] == 1

    # 행 자체는 살아 있다
    from app import db

    with db.cursor() as conn:
        row = conn.execute(
            "SELECT deleted_at FROM entries WHERE id = %s", (made["id"],)
        ).fetchone()
    assert row["deleted_at"] is not None

    # 지워진 글은 더 이상 손댈 수 없다
    assert (
        client.patch(
            f"/api/entries/{made['id']}",
            json={"content": "x"},
            headers={"X-Edit-Token": made["edit_token"]},
        ).status_code
        == 404
    )


# ---------- PIN ----------


def test_verify_returns_temp_token(client, make_entry):
    made = make_entry(content="원문", pin="4321")
    r = client.post(f"/api/entries/{made['id']}/verify", json={"pin": "4321"})
    assert r.status_code == 200

    temp = r.json()["edit_token"]
    assert r.json()["content"] == "원문"
    assert temp != made["edit_token"]  # 영구 토큰을 그대로 주지 않는다

    ok = client.patch(
        f"/api/entries/{made['id']}",
        json={"content": "다른 기기에서 수정"},
        headers={"X-Edit-Token": temp},
    )
    assert ok.status_code == 200


def test_temp_token_survives_process_restart(client, make_entry):
    """토큰이 process 안에 저장되지 않는다. instance가 갈려도 통해야 한다."""
    made = make_entry(pin="4321")
    temp = client.post(
        f"/api/entries/{made['id']}/verify", json={"pin": "4321"}
    ).json()["edit_token"]

    # verify를 처리한 instance가 죽고 다른 instance가 PATCH를 받는 상황.
    # 저장된 상태가 있었다면 여기서 전부 날아간다.
    importlib.reload(security)

    r = client.patch(
        f"/api/entries/{made['id']}",
        json={"content": "다른 instance에서 수정"},
        headers={"X-Edit-Token": temp},
    )
    assert r.status_code == 200


def test_temp_token_is_scoped_to_one_entry(client, make_entry):
    """A글로 받은 토큰이 B글에 통하면 안 된다"""
    a = make_entry(content="내 글", pin="1111")
    b = make_entry(content="남의 글", pin="2222")

    temp = client.post(f"/api/entries/{a['id']}/verify", json={"pin": "1111"}).json()[
        "edit_token"
    ]
    r = client.patch(
        f"/api/entries/{b['id']}",
        json={"content": "남의 글 수정"},
        headers={"X-Edit-Token": temp},
    )
    assert r.status_code == 401


def test_temp_token_rejects_tampering(client, make_entry):
    """서명이 안 맞으면 거부한다. entry_id만 바꿔치기하는 경우 포함"""
    a = make_entry(pin="1111")
    b = make_entry(pin="2222")
    temp = client.post(f"/api/entries/{a['id']}/verify", json={"pin": "1111"}).json()[
        "edit_token"
    ]
    _, exp, sig = temp.split(".")

    forged = f"{b['id']}.{exp}.{sig}"  # id만 갈아끼운다
    assert not security.verify_temp_token(forged, b["id"])
    assert not security.verify_temp_token(temp[:-1] + "0", a["id"])  # 서명 훼손
    assert not security.verify_temp_token("garbage", a["id"])


def test_temp_token_expires(client, make_entry):
    made = make_entry(pin="1111")
    assert security.verify_temp_token(security.issue_temp_token(made["id"]), made["id"])

    with mock.patch.object(config, "TEMP_TOKEN_TTL_SECONDS", -1):
        stale = security.issue_temp_token(made["id"])
    assert not security.verify_temp_token(stale, made["id"])


def test_pin_lockout(client, make_entry):
    """5회 실패 후에는 올바른 PIN도 423"""
    made = make_entry(pin="1234")
    for _ in range(config.PIN_MAX_ATTEMPTS):
        assert (
            client.post(f"/api/entries/{made['id']}/verify", json={"pin": "0000"}).status_code
            == 401
        )
    r = client.post(f"/api/entries/{made['id']}/verify", json={"pin": "1234"})
    assert r.status_code == 423


def test_failed_attempts_reset_on_success(client, make_entry):
    made = make_entry(pin="1234")
    client.post(f"/api/entries/{made['id']}/verify", json={"pin": "0000"})
    assert client.post(f"/api/entries/{made['id']}/verify", json={"pin": "1234"}).status_code == 200

    from app import db

    with db.cursor() as conn:
        row = conn.execute(
            "SELECT failed_attempts, locked_until FROM entries WHERE id = %s", (made["id"],)
        ).fetchone()
    assert row["failed_attempts"] == 0
    assert row["locked_until"] is None


# ---------- 사진 ----------


def test_photo_exif_stripped(client, make_entry):
    """GPS가 박힌 사진을 올린 뒤 저장된 바이트에 EXIF가 없어야 한다"""
    make_entry(photo=("home.jpg", photo_bytes(), "image/jpeg"))

    entry = client.get("/api/entries").json()["entries"][0]
    assert entry["photo"].startswith("/media/")
    assert entry["photo"].endswith(".webp")

    served = client.get(entry["photo"])
    assert served.headers["content-type"] == "image/webp"

    with Image.open(io.BytesIO(served.content)) as img:
        assert not dict(img.getexif())
        assert max(img.size) <= config.MAX_PHOTO_EDGE


def test_photo_served(client, make_entry):
    make_entry(photo=("home.jpg", photo_bytes(with_gps=False), "image/jpeg"))
    path = client.get("/api/entries").json()["entries"][0]["photo"]
    r = client.get(path)
    assert r.status_code == 200
    # 사진을 DB에서 꺼내는 이상 브라우저가 매번 다시 받아가면 안 된다.
    assert "immutable" in r.headers["cache-control"]


def test_photo_survives_soft_delete(client, make_entry):
    """글을 지워도 사진 행은 남는다. 복구할 때 같이 살아나야 한다."""
    made = make_entry(photo=("home.jpg", photo_bytes(with_gps=False), "image/jpeg"))
    path = client.get("/api/entries").json()["entries"][0]["photo"]

    client.delete(f"/api/entries/{made['id']}", headers={"X-Edit-Token": made["edit_token"]})
    assert client.get(path).status_code == 200


def test_photo_rejects_non_image(client):
    r = client.post(
        "/api/entries",
        data={"name": "은지", "content": "위장", "pin": "1234"},
        files={"photo": ("evil.jpg", b"not an image at all", "image/jpeg")},
    )
    assert r.status_code == 400


def test_photo_rejects_oversize(client):
    r = client.post(
        "/api/entries",
        data={"name": "은지", "content": "큰 파일", "pin": "1234"},
        files={"photo": ("big.jpg", b"\xff" * (config.MAX_PHOTO_BYTES + 1), "image/jpeg")},
    )
    assert r.status_code == 400


def test_media_missing(client):
    assert client.get("/media/..%2Fguestbook.db").status_code == 404
    assert client.get("/media/nope.webp").status_code == 404


# ---------- 비밀글 ----------


def test_secret_content_never_leaks(client, make_entry):
    made = make_entry(content="비밀 이야기")
    from app import db

    with db.cursor() as conn:
        conn.execute("UPDATE entries SET is_secret = TRUE WHERE id = %s", (made["id"],))

    for e in client.get("/api/entries").json()["entries"]:
        if e["is_secret"]:
            assert "content" not in e
            assert "reply" not in e
