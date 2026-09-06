import os
from pathlib import Path

# Neon은 pooled endpoint(-pooler가 붙은 host)를 쓴다. Cloud Run이 instance를 계속
# 만들고 버리는 탓에 direct endpoint로 붙으면 connection이 금방 동난다.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://guestbook:devpass@127.0.0.1:5433/guestbook")

IP_HASH_SALT = os.getenv("IP_HASH_SALT", "dev-salt-change-me")

# 정적 프론트 빌드 결과물. 없으면 API만 서빙한다.
STATIC_DIR = Path(os.getenv("STATIC_DIR", "./static"))

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_EDGE = 1600

# 사진 파일명은 서버가 만든 랜덤 hex다. 내용이 바뀌는 일이 없으니 영구 캐시로 준다.
PHOTO_CACHE_CONTROL = "public, max-age=31536000, immutable"

PIN_MAX_ATTEMPTS = 5
PIN_LOCK_SECONDS = 60 * 60
TEMP_TOKEN_TTL_SECONDS = 10 * 60

FEED_DEFAULT_LIMIT = 20
FEED_MAX_LIMIT = 100
