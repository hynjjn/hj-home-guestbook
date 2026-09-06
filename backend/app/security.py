import hashlib
import hmac
import secrets
import time

import bcrypt

from . import config


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def check_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def new_edit_token() -> str:
    return secrets.token_hex(32)


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256((config.IP_HASH_SALT + ip).encode()).hexdigest()


# ---------- verify가 발급하는 임시 토큰 ----------
#
# 서버에 저장하지 않고 서명만으로 검증한다. instance가 여러 개 뜨고 idle하면
# 사라지는 환경에서는 process 안의 dict가 답이 될 수 없다. verify를 처리한
# instance와 PATCH를 처리한 instance가 다르면 그대로 401이 되기 때문이다.
#
# 형식은 "{entry_id}.{만료 epoch}.{서명}". monotonic이 아니라 벽시계를 쓰는 이유는
# monotonic이 process마다 기준점이 달라 instance 사이에서 비교가 안 되기 때문이다.


def _sign(payload: str) -> str:
    return hmac.new(
        config.TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def issue_temp_token(entry_id: int) -> str:
    payload = f"{entry_id}.{int(time.time()) + config.TEMP_TOKEN_TTL_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def verify_temp_token(token: str, entry_id: int) -> bool:
    """서명이 맞고, 이 글에 대해 발급됐고, 아직 안 지났으면 True."""
    parts = token.split(".")
    if len(parts) != 3:
        return False
    raw_id, raw_exp, signature = parts

    # 서명을 먼저 본다. 값을 신뢰하기 전에 위조부터 걸러낸다.
    if not hmac.compare_digest(signature, _sign(f"{raw_id}.{raw_exp}")):
        return False
    if raw_id != str(entry_id):
        return False
    try:
        return int(raw_exp) > time.time()
    except ValueError:
        return False


def token_matches(given: str, stored: str) -> bool:
    return hmac.compare_digest(given, stored)
