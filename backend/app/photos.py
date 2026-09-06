import io
import secrets

from PIL import Image

from . import config


class PhotoError(ValueError):
    pass


def encode_photo(raw: bytes) -> tuple[str, bytes]:
    """디코딩 후 새 파일로 재인코딩한다. EXIF 제거, 확장자 위조 검증, polyglot 무력화를 한 번에 처리한다.

    저장은 하지 않고 (파일명, WEBP 바이트)만 돌려준다. 실제 쓰기는 photos 테이블에서 한다.
    """
    if len(raw) > config.MAX_PHOTO_BYTES:
        raise PhotoError("too large")

    try:
        img = Image.open(io.BytesIO(raw))  # 실패하면 이미지가 아니다
        img.verify()
        img = Image.open(io.BytesIO(raw))  # verify는 지연 로딩을 소모하므로 다시 연다
        img = img.convert("RGB")  # EXIF, 알파, 팔레트 정보가 여기서 사라진다
        img.thumbnail((config.MAX_PHOTO_EDGE, config.MAX_PHOTO_EDGE))
    except PhotoError:
        raise
    except Exception as exc:
        raise PhotoError("not an image") from exc

    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=82, method=4)
    return secrets.token_hex(8) + ".webp", buf.getvalue()
