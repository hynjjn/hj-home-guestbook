import os
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "./data/guestbook.db"))
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "./data/media"))
IP_HASH_SALT = os.getenv("IP_HASH_SALT", "dev-salt-change-me")

# 정적 프론트 빌드 결과물. 없으면 API만 서빙한다.
STATIC_DIR = Path(os.getenv("STATIC_DIR", "./static"))

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_EDGE = 1600

PIN_MAX_ATTEMPTS = 5
PIN_LOCK_SECONDS = 60 * 60
TEMP_TOKEN_TTL_SECONDS = 10 * 60

FEED_DEFAULT_LIMIT = 20
FEED_MAX_LIMIT = 100
