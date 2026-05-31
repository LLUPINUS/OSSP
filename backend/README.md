# Backend

프로젝트의 백엔드 서버 + 데이터베이스 영역입니다.

## 기술 스택

| 분류 | 사용 기술 | 버전 |
|------|-----------|------|
| 언어 | Python | 3.11 |
| 웹 프레임워크 | FastAPI | 0.136.1 |
| ASGI 서버 | Uvicorn | 0.32.1 |
| ORM | SQLAlchemy | 2.0.48 |
| 마이그레이션 | Alembic | 1.18.4 |
| DB | PostgreSQL | 18 |
| 비동기 DB 드라이버 | asyncpg | 0.30.0 |
| 동기 DB 드라이버 | psycopg2-binary | 2.9.10 |

전체 패키지 목록은 `requirements.txt` 참고.

## 처음 세팅하기

### 사전 준비

- Python 3.11 설치
- PostgreSQL 18 설치 및 실행 중인 상태
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

### 6. 마이그레이션 적용

```bash
alembic upgrade head
```

이 한 번으로 4개 테이블(`recipes`·`transcripts`·`action_labels`·`cooking_steps`)이 생성되고, 행동 라벨 시드 데이터(썰기·굽기·볶기·젓기)까지 자동으로 적용됩니다.

### 7. 개발 서버 실행

```bash
uvicorn main:app --reload
```

서버가 켜지면 다음 URL로 접속 가능:
- API 서버: http://localhost:8000
- 자동 생성된 API 문서 (Swagger UI): http://localhost:8000/docs
- 대안 API 문서 (ReDoc): http://localhost:8000/redoc

`--reload` 옵션은 코드 변경 시 자동으로 서버를 재시작합니다. 개발 중에만 사용하세요.

## 폴더 구조

```
backend/
├── app/
│   ├── core/                # 설정, DB 연결
│   │   ├── config.py        # 환경변수 로드 (Settings)
│   │   └── database.py      # SQLAlchemy 비동기 엔진/세션
│   └── models/              # SQLAlchemy 모델 (1 테이블 = 1 파일)
│       ├── recipe.py
│       ├── transcript.py
│       ├── action_label.py
│       └── cooking_step.py
├── api/                     # 외부 API 클라이언트 + DB 서비스 계층
│   ├── youtube_search.py    # YouTube Data API 검색
│   ├── transcript.py        # 자막 추출
│   ├── gemini_parser.py     # Gemini 단계 분류
│   └── db_service.py        # DB 저장/조회/캐싱
├── alembic/
│   ├── env.py
│   └── versions/            # 마이그레이션 스크립트
├── main.py                  # FastAPI 진입점
├── alembic.ini
├── requirements.txt
└── .env.example
```

> 구조는 작업 진행에 따라 계속 정리됩니다 (`app/`와 `api/`의 통합 방향은 협의 중).

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
PostgreSQL이 시스템에 설치되어 있지 않으면 발생할 수 있습니다. PostgreSQL 18이 설치되어 있는지 확인하세요.

### DB 연결 실패
- PostgreSQL 서비스가 실행 중인지 확인
- `.env`의 `DATABASE_URL`에 적힌 비밀번호가 정확한지 확인
- 포트번호가 5432가 맞는지 확인 (다른 포트로 설치한 경우 변경)