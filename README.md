# 집 방명록

집에 온 손님이 QR을 찍고 한마디 남기는 방명록. 로그인 없이 누구나 쓰고, 누구나 읽는다.
설계 근거와 안 만들기로 한 것들은 [docs/SPEC.md](docs/SPEC.md)에 있다.

## 구성

```
backend/    FastAPI + Postgres. 정적 프론트도 여기서 서빙한다
frontend/   React + Vite. 빌드 결과가 backend/static으로 들어간다
```

## 로컬 실행

Postgres부터 띄운다. 다른 컨테이너와 안 겹치게 5433으로 연다.

```bash
docker run -d --name guestbook-pg \
  -e POSTGRES_USER=guestbook -e POSTGRES_DB=guestbook -e POSTGRES_PASSWORD=devpass \
  -p 5433:5432 postgres:17-alpine
```

그다음 터미널 두 개를 쓴다. `DATABASE_URL` 기본값이 위 컨테이너를 가리키므로 따로 안 넘겨도 된다.

```bash
# 1) API
cd backend
uv run uvicorn app.main:app --reload

# 2) 프론트. /api와 /media는 8000번으로 proxy된다
cd frontend
npm install
npm run dev
```

한 곳에서 띄우려면 프론트를 빌드한 뒤 API만 실행하면 된다.

```bash
cd frontend && npm run build     # backend/static에 떨어진다
cd ../backend && uv run uvicorn app.main:app
```

## 테스트

```bash
cd backend && uv run pytest
```

## 배포

```bash
cp .env.example .env             # IP_HASH_SALT, TUNNEL_TOKEN을 채운다
docker compose up -d --build
```

`app`은 host에 포트를 열지 않고 `cloudflared`가 outbound로만 나간다. port forwarding,
DDNS, 공인 IP가 전부 불필요하고 집 IP도 노출되지 않는다.

Mac이 Apple Silicon이고 파이가 64bit OS면 둘 다 arm64라 Mac에서 빌드해 push하면 그대로 돈다.

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | local 컨테이너 | Postgres 접속 문자열. Neon은 pooled endpoint를 쓴다 |
| `STATIC_DIR` | `./static` | 프론트 빌드 결과물. 없으면 API만 서빙한다 |
| `IP_HASH_SALT` | `dev-salt-change-me` | ip_hash용 salt. 배포에서는 반드시 바꾼다 |

관리자 토큰은 없다. 주인장은 답글, 삭제, 검열을 전부 SQL로 처리한다.

```bash
psql "$DATABASE_URL" -c \
  "UPDATE entries SET owner_reply = '다음에 보여줄게', owner_reply_at = now()::text WHERE id = 187"
```

## 백업

사진 바이트가 `photos` 테이블에 들어 있으므로 dump 하나가 곧 완전한 스냅샷이다.
DB와 파일 저장소가 서로 어긋난 채로 복구되는 경우가 아예 없다.

```bash
pg_dump "$DATABASE_URL" -Fc -f "backup-$(date +%F).dump"
```

Neon이 주는 PITR은 Neon 쪽 사고를 막아 줄 뿐이다. 이쪽 실수는 못 막으니 위 dump를
따로 굴린다.

## 폰트

Mona12는 `frontend/public/fonts`에 self-host한다. SIL OFL 1.1이라 재배포에 문제없고,
라이선스 전문은 같은 폴더의 `OFL.txt`에 있다. 12px 비트맵 폰트라 크기는 12의 배수만 쓴다.
입력창 16px만 예외다. iOS Safari가 16px 미만 입력에 포커스하면 페이지를 확대한 뒤
되돌리지 않는다.
