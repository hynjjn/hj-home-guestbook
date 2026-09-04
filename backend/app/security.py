import hashlib
import hmac
import secrets
import time

import bcrypt

from . import config

# verify가 발급하는 10분짜리 일회성 토큰. entries.edit_token은 절대 그대로 주지 않는다.
_temp_tokens: dict[str, tuple[int, float]] = {}


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


def issue_temp_token(entry_id: int) -> str:
    _prune()
    token = secrets.token_hex(32)
    _temp_tokens[token] = (entry_id, time.monotonic() + config.TEMP_TOKEN_TTL_SECONDS)
    return token


def consume_temp_token(token: str, entry_id: int) -> bool:
    """유효하면 True. 만료된 항목은 정리한다."""
    _prune()
    for candidate, (owner_id, _expires) in _temp_tokens.items():
        if owner_id == entry_id and hmac.compare_digest(candidate, token):
            return True
    return False


def drop_tokens_for(entry_id: int) -> None:
    for token in [t for t, (owner, _) in _temp_tokens.items() if owner == entry_id]:
        _temp_tokens.pop(token, None)


def _prune() -> None:
    now = time.monotonic()
    for token in [t for t, (_, expires) in _temp_tokens.items() if expires <= now]:
        _temp_tokens.pop(token, None)


def token_matches(given: str, stored: str) -> bool:
    return hmac.compare_digest(given, stored)
