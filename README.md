# 집 방명록

집에 온 손님이 QR을 찍고 한마디 남기는 방명록. 로그인 없이 누구나 쓰고, 누구나 읽는다.
설계 근거와 안 만들기로 한 것들은 [docs/SPEC.md](docs/SPEC.md)에 있다.

## 구성

```
backend/    FastAPI + Postgres. API만 서빙한다. Cloud Run에 올라간다
frontend/   React + Vite. Vercel에 올라간다
```

## 로컬 실행

Postgres부터 띄운다. 다른 컨테이너와 안 겹치게 5433으로 연다.

```bash
docker compose up -d db
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


## 테스트

```bash
cd backend && uv run pytest
```

## 배포

프론트는 Vercel, API는 Cloud Run, DB는 Neon이다. 도메인 없이 `*.vercel.app`과
`*.run.app`만으로 돌아간다.

### 1. Cloud Run

Neon이 Singapore에 있으므로 region을 맞춘다. 어긋나면 질의마다 왕복 지연을 그대로 문다.

```bash
gcloud run deploy guestbook \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-secrets DATABASE_URL=guestbook-db-url:latest \
  --set-secrets IP_HASH_SALT=guestbook-ip-salt:latest \
  --set-secrets TOKEN_SECRET=guestbook-token-secret:latest
```

Apple Silicon에서 로컬 빌드해 올릴 때는 `--platform linux/amd64`를 붙인다. `--source`를
쓰면 Cloud Build가 알아서 맞춰 준다.

### 2. Vercel

`frontend/`를 root directory로 잡는다. `frontend/vercel.json`의 `REPLACE-ME`를 1번에서
받은 Cloud Run 주소로 바꾸면 `/api`와 `/media`가 그쪽으로 넘어간다. same-origin이라
CORS 설정이 아예 필요 없다.

### 시크릿

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

`IP_HASH_SALT`와 `TOKEN_SECRET`을 각각 따로 만들어 Secret Manager에 넣는다.
`TOKEN_SECRET`은 **instance가 여러 개여도 전부 같은 값**이어야 한다. process마다
다른 값을 쓰면 verify한 instance와 PATCH를 받는 instance가 갈릴 때 401이 난다.

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | local 컨테이너 | Postgres 접속 문자열. Neon은 pooled endpoint를 쓴다 |
| `IP_HASH_SALT` | `dev-salt-change-me` | ip_hash용 salt. 배포에서는 반드시 바꾼다 |
| `TOKEN_SECRET` | `dev-token-secret-change-me` | 임시 토큰 서명용. 모든 instance가 같은 값을 봐야 한다 |
| `PORT` | `8080` | Cloud Run이 넣어 준다 |

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
