import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import psycopg
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, security
from .photos import PhotoError, encode_photo

PIN_RE = re.compile(r"^\d{4}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(title="집 방명록", lifespan=lifespan)


def get_conn():
    with db.cursor() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def client_ip(request: Request) -> str | None:
    # Cloudflare Tunnel 뒤에서는 request.client.host가 전부 같은 값이다.
    return request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else None
    )


def serialize(row: dict[str, Any], *, mine: bool, is_owner: bool = False) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": row["id"],
        "name": row["name"],
        "content": row["content"],
        "is_secret": bool(row["is_secret"]),
        "photo": f"/media/{row['photo']}" if row["photo"] else None,
        "reply": (
            {"content": row["owner_reply"], "at": row["owner_reply_at"]}
            if row["owner_reply"]
            else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "mine": mine,
    }
    # 비밀글은 프론트에서 가리는 게 아니라 서버가 키 자체를 응답에 담지 않는다.
    if base["is_secret"] and not is_owner:
        base.pop("content", None)
        base.pop("reply", None)
    return base


def fetch_alive(conn: psycopg.Connection, entry_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM entries WHERE id = %s AND deleted_at IS NULL", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "없는 글이에요")
    return row


def authorize(row: dict[str, Any], given: str | None) -> None:
    """영구 토큰 또는 verify가 발급한 임시 토큰이면 통과."""
    if not given:
        raise HTTPException(401, "권한이 없어요")
    if security.token_matches(given, row["edit_token"]):
        return
    if security.consume_temp_token(given, row["id"]):
        return
    raise HTTPException(401, "권한이 없어요")


# ---------- GET /api/entries ----------


@app.get("/api/entries")
def list_entries(
    conn: Conn,
    limit: int = config.FEED_DEFAULT_LIMIT,
    before: int | None = None,
    x_edit_tokens: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, config.FEED_MAX_LIMIT))
    tokens = {t.strip() for t in (x_edit_tokens or "").split(",") if t.strip()}

    sql = "SELECT * FROM entries WHERE deleted_at IS NULL"
    params: list[Any] = []
    if before is not None:
        sql += " AND id < %s"
        params.append(before)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit + 1)

    rows = conn.execute(sql, params).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE deleted_at IS NULL"
    ).fetchone()["n"]

    entries = [
        serialize(
            row,
            mine=any(security.token_matches(t, row["edit_token"]) for t in tokens),
        )
        for row in rows
    ]
    return {"entries": entries, "total": total, "has_more": has_more}


# ---------- POST /api/entries ----------


@app.post("/api/entries", status_code=201)
async def create_entry(
    request: Request,
    conn: Conn,
    name: Annotated[str, Form()],
    content: Annotated[str, Form()],
    pin: Annotated[str, Form()],
    photo: Annotated[UploadFile | None, File()] = None,
) -> dict[str, Any]:
    name = name.strip()
    content = content.strip()

    if not 1 <= len(name) <= 12:
        raise HTTPException(422, "이름은 1~12자로 넣어 주세요")
    if not 1 <= len(content) <= 1000:
        raise HTTPException(422, "내용은 1~1000자로 넣어 주세요")
    if not PIN_RE.fullmatch(pin):
        raise HTTPException(422, "숫자 4자리를 넣어 주세요")

    filename = data = None
    if photo is not None and photo.filename:
        raw = await photo.read()
        if raw:
            try:
                filename, data = encode_photo(raw)
            except PhotoError:
                raise HTTPException(400, "사진을 읽을 수 없어요") from None

    token = security.new_edit_token()
    # 사진과 글은 같이 들어가거나 같이 실패해야 한다. 따로 쓰면 참조되지 않는
    # photos 행이 남는다.
    with conn.transaction():
        if filename is not None:
            conn.execute("INSERT INTO photos (name, data) VALUES (%s, %s)", (filename, data))
        row = conn.execute(
            """INSERT INTO entries (name, content, pin_hash, edit_token, photo, ip_hash, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                name,
                content,
                security.hash_pin(pin),
                token,
                filename,
                security.hash_ip(client_ip(request)),
                now_iso(),
            ),
        ).fetchone()
    # edit_token은 이 응답에서만 내려간다.
    return {"id": row["id"], "edit_token": token}


# ---------- POST /api/entries/{id}/verify ----------


class VerifyBody(BaseModel):
    pin: str = Field(min_length=4, max_length=4)


@app.post("/api/entries/{entry_id}/verify")
def verify_pin(entry_id: int, body: VerifyBody, conn: Conn) -> dict[str, str]:
    row = fetch_alive(conn, entry_id)

    locked_until = row["locked_until"]
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(UTC):
        # 잠긴 동안에는 PIN이 맞아도 통과시키지 않는다.
        raise HTTPException(423, "잠시 뒤에 다시 시도해 주세요")

    if not security.check_pin(body.pin, row["pin_hash"]):
        attempts = row["failed_attempts"] + 1
        if attempts >= config.PIN_MAX_ATTEMPTS:
            until = datetime.now(UTC) + timedelta(seconds=config.PIN_LOCK_SECONDS)
            conn.execute(
                "UPDATE entries SET failed_attempts = 0, locked_until = %s WHERE id = %s",
                (until.isoformat(), entry_id),
            )
        else:
            conn.execute(
                "UPDATE entries SET failed_attempts = %s WHERE id = %s",
                (attempts, entry_id),
            )
        raise HTTPException(401, "숫자가 맞지 않아요")

    conn.execute(
        "UPDATE entries SET failed_attempts = 0, locked_until = NULL WHERE id = %s",
        (entry_id,),
    )
    return {"edit_token": security.issue_temp_token(entry_id), "content": row["content"]}


# ---------- PATCH / DELETE ----------


class PatchBody(BaseModel):
    content: str


@app.patch("/api/entries/{entry_id}")
def update_entry(
    entry_id: int,
    body: PatchBody,
    conn: Conn,
    x_edit_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    row = fetch_alive(conn, entry_id)
    authorize(row, x_edit_token)

    content = body.content.strip()
    if not 1 <= len(content) <= 1000:
        raise HTTPException(422, "내용은 1~1000자로 넣어 주세요")

    conn.execute(
        "UPDATE entries SET content = %s, updated_at = %s WHERE id = %s",
        (content, now_iso(), entry_id),
    )
    updated = fetch_alive(conn, entry_id)
    return serialize(updated, mine=True)


@app.delete("/api/entries/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    conn: Conn,
    x_edit_token: Annotated[str | None, Header()] = None,
) -> Response:
    row = fetch_alive(conn, entry_id)
    authorize(row, x_edit_token)
    # soft delete. 사진 파일은 남긴다. 복구할 때 같이 살아나야 한다.
    conn.execute(
        "UPDATE entries SET deleted_at = %s WHERE id = %s", (now_iso(), entry_id)
    )
    security.drop_tokens_for(entry_id)
    return Response(status_code=204)


# ---------- 정적 서빙 ----------


@app.get("/media/{filename}")
def media(filename: str, conn: Conn) -> Response:
    # 파일 경로를 만들지 않고 primary key로 찾는다. 경로 조작이라는 개념 자체가 없다.
    row = conn.execute("SELECT data FROM photos WHERE name = %s", (filename,)).fetchone()
    if row is None:
        raise HTTPException(404, "없는 사진이에요")
    return Response(
        bytes(row["data"]),
        media_type="image/webp",
        headers={"Cache-Control": config.PHOTO_CACHE_CONTROL},
    )


if config.STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
