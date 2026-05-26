"""
애플리케이션 설정 로더.

.env 파일과 환경 변수에서 값을 읽어 타입이 검증된 Settings 객체로 만든다.
앱 어디서든 `from app.core.config import settings`로 가져다 쓴다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 전역 설정. 각 필드는 .env의 같은 이름 키와 매핑된다."""

    # === Database ===
    DATABASE_URL: str           # FastAPI 비동기 연결용 (asyncpg)
    ALEMBIC_DATABASE_URL: str   # Alembic 마이그레이션용 (psycopg2, 동기)
    TEST_DATABASE_URL: str | None = None  # 통합 테스트용 (asyncpg). 없으면 DB 테스트 skip

    # === External API Keys ===
    YOUTUBE_API_KEY: str
    GEMINI_API_KEY: str

    # === AI Inference Server ===
    AI_SERVER_URL: str

    # === Application Settings ===
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    # .env 파일 위치와 인코딩 지정
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# 앱 전역에서 공유할 단일 인스턴스
settings = Settings()