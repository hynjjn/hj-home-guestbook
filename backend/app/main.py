import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, security
from .photos import PhotoError, save_photo

PIN_RE = re.compile(r"^\d{4}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    config.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="집 방명록", lifespan=lifespan)


def get_conn():
    with db.cursor() as conn:
        yield conn


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def client_ip(request: Request) -> str | None:
    # Cloudflare Tunnel 뒤에서는 request.client.host가 전부 같은 값이다.
    return request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else None
    )


def serialize(row: sqlite3.Row, *, mine: bool, is_owner: bool = False) -> dict[str, Any]:
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


def fetch_alive(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM entries WHERE id = ? AND deleted_at IS NULL", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "없는 글이에요")
    return row


def authorize(row: sqlite3.Row, given: str | None) -> None:
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
        sql += " AND id < ?"
        params.append(before)
    sql += " ORDER BY id DESC LIMIT ?"
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

    filename = None
    if photo is not None and photo.filename:
        raw = await photo.read()
        if raw:
            try:
                filename = save_photo(raw)
            except PhotoError:
                raise HTTPException(400, "사진을 읽을 수 없어요") from None

    token = security.new_edit_token()
    cur = conn.execute(
        """INSERT INTO entries (name, content, pin_hash, edit_token, photo, ip_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            content,
            security.hash_pin(pin),
            token,
            filename,
            security.hash_ip(client_ip(request)),
            now_iso(),
        ),
    )
    # edit_token은 이 응답에서만 내려간다.
    return {"id": cur.lastrowid, "edit_token": token}


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
                "UPDATE entries SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                (until.isoformat(), entry_id),
            )
        else:
            conn.execute(
                "UPDATE entries SET failed_attempts = ? WHERE id = ?",
                (attempts, entry_id),
            )
        raise HTTPException(401, "숫자가 맞지 않아요")

    conn.execute(
        "UPDATE entries SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
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
        "UPDATE entries SET content = ?, updated_at = ? WHERE id = ?",
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
        "UPDATE entries SET deleted_at = ? WHERE id = ?", (now_iso(), entry_id)
    )
    security.drop_tokens_for(entry_id)
    return Response(status_code=204)


# ---------- 정적 서빙 ----------


@app.get("/media/{filename}")
def media(filename: str) -> FileResponse:
    # 파일명은 서버가 만든 랜덤 hex뿐이지만 경로 조작은 한 번 더 막는다.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "잘못된 경로예요")
    path = config.MEDIA_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "없는 사진이에요")
    return FileResponse(path)


if config.STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
