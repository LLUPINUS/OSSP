# Backend

프로젝트의 백엔드 서버 + 데이터베이스 영역입니다.

## 기술 스택

| 분류 | 사용 기술 | 버전 |
|------|-----------|------|
| 언어 | Python | 3.12 |
| 웹 프레임워크 | FastAPI | 0.136.1 |
| ASGI 서버 | Uvicorn | 0.32.1 |
| ORM | SQLAlchemy | 2.0.48 |
| 마이그레이션 | Alembic | 1.18.4 |
| DB | PostgreSQL | 14 이상 |
| 비동기 DB 드라이버 | asyncpg | 0.30.0 |
| 동기 DB 드라이버 | psycopg2-binary | 2.9.10 |

전체 패키지 목록은 `requirements.txt` 참고.

## 처음 세팅하기

### 사전 준비

- Python 3.12 설치
- PostgreSQL 14 이상 설치 및 실행 중인 상태
- pgAdmin4 (선택사항, DB 확인용)

### 1. backend 폴더로 이동

```bash
cd backend
```

### 2. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

가상환경이 활성화되면 터미널 프롬프트 앞에 `(.venv)`가 표시됩니다.

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 파일 생성

`.env.example` 파일을 복사해서 `.env`로 이름을 바꾼 뒤, 본인 환경에 맞게 값을 채웁니다.

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

VS Code에서 `.env` 파일을 열어 다음 값들을 채우세요:
- `DATABASE_URL`: 본인 PostgreSQL 비밀번호 입력
- `YOUTUBE_API_KEY`: 팀에서 공유한 YouTube Data API 키
- `GEMINI_API_KEY`: 팀에서 공유한 Gemini API 키

> ⚠️ `.env` 파일은 `.gitignore`에 등록되어 있어 GitHub에 올라가지 않습니다. 비밀번호와 API 키가 노출되지 않도록 절대 직접 추가하지 마세요.

### 5. PostgreSQL에 DB 생성

pgAdmin4 또는 psql에서 다음 명령으로 DB 생성:

```sql
CREATE DATABASE cooksync;
```

### 6. 마이그레이션 적용 (Alembic 세팅 후)

```bash
alembic upgrade head
```

> 처음 세팅 시점에는 아직 Alembic이 초기화되지 않았을 수 있습니다. 초기화는 별도 작업으로 진행 예정입니다.

### 7. 개발 서버 실행

```bash
uvicorn main:app --reload
```

서버가 켜지면 다음 URL로 접속 가능:
- API 서버: http://localhost:8000
- 자동 생성된 API 문서 (Swagger UI): http://localhost:8000/docs
- 대안 API 문서 (ReDoc): http://localhost:8000/redoc

`--reload` 옵션은 코드 변경 시 자동으로 서버를 재시작합니다. 개발 중에만 사용하세요.

## 폴더 구조 (예정)

```
backend/
├── app/
│   ├── main.py              # FastAPI 진입점
│   ├── core/                # 설정, DB 연결
│   │   ├── config.py        # 환경변수 로드
│   │   └── database.py      # SQLAlchemy 세션
│   ├── models/              # SQLAlchemy 모델
│   ├── schemas/             # Pydantic 요청/응답 스키마
│   ├── api/routes/          # API 엔드포인트
│   ├── crud/                # DB 조회/수정 함수
│   └── services/            # 외부 API 호출 등 비즈니스 로직
├── alembic/
│   ├── env.py
│   └── versions/            # 마이그레이션 스크립트
├── tests/
├── alembic.ini
├── requirements.txt
└── .env.example
```

실제 폴더는 작업이 진행되면서 단계적으로 추가됩니다.

## 자주 쓰는 명령어

### Alembic 마이그레이션

```bash
# 모델 변경 후 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "<변경 내용 설명>"

# 마이그레이션 적용
alembic upgrade head

# 직전 마이그레이션 되돌리기
alembic downgrade -1

# 현재 적용된 리비전 확인
alembic current
```

### 패키지 추가 후 requirements.txt 갱신

새 패키지를 설치한 뒤에는 반드시 `requirements.txt`에 반영해야 팀원들의 환경과 동기화됩니다.

```bash
pip install <패키지명>
pip freeze > requirements.txt
```

## 트러블슈팅

### `ModuleNotFoundError: No module named 'app'`
가상환경이 활성화되지 않았거나, `backend/` 폴더가 아닌 다른 곳에서 실행 중일 가능성이 높습니다. 다음 확인:
- 터미널 프롬프트 앞에 `(.venv)`가 보이는지
- 현재 위치가 `backend/` 폴더인지 (`pwd` 또는 `cd`)

### `psycopg2` 또는 `asyncpg` 설치 실패
PostgreSQL이 시스템에 설치되어 있지 않으면 발생할 수 있습니다. PostgreSQL 14 이상이 설치되어 있는지 확인하세요.

### DB 연결 실패
- PostgreSQL 서비스가 실행 중인지 확인
- `.env`의 `DATABASE_URL`에 적힌 비밀번호가 정확한지 확인
- 포트번호가 5432가 맞는지 확인 (다른 포트로 설치한 경우 변경)