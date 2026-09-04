import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    content         TEXT    NOT NULL,

    pin_hash        TEXT    NOT NULL,
    edit_token      TEXT    NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,

    is_secret       INTEGER NOT NULL DEFAULT 0,
    photo           TEXT,
    owner_reply     TEXT,
    owner_reply_at  TEXT,

    ip_hash         TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT,
    deleted_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_feed ON entries (deleted_at, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_token ON entries (edit_token);
"""


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 요청마다 새 연결을 만들고 한 번에 한 스레드만 쓴다. FastAPI가 sync 의존성을
    # threadpool에서 돌리고 async 엔드포인트는 event loop에서 도는 탓에 스레드가 갈린다.
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL을 안 켜면 읽는 동안 쓰기가 막힌다.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init() -> None:
    with cursor() as conn:
        conn.executescript(SCHEMA)
