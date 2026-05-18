"""
FastAPI 애플리케이션 엔트리포인트.

uvicorn이 이 파일의 `app` 객체를 찾아 서버로 실행한다.
실행 예: uvicorn app.main:app --reload
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db


# === FastAPI 인스턴스 ===
app = FastAPI(
    title="OSSP API",
    description="실시간 CV 기반 유튜브 요리 영상 제어 서비스 백엔드",
    version="0.1.0",
)


# === CORS 미들웨어 ===
# .env의 CORS_ORIGINS는 콤마로 여러 출처를 구분할 수 있게 분리해서 리스트로 만든다.
# 예: "http://localhost:5173,http://localhost:3000"
allowed_origins = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 헬스체크 엔드포인트 ===

@app.get("/")
async def root():
    """앱 자체 헬스체크. 서버 프로세스가 살아있는지 확인."""
    return {
        "service": "CookSync API",
        "status": "ok",
        "debug": settings.DEBUG,
    }


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """DB 연결 헬스체크. PostgreSQL과 통신이 가능한지 확인."""
    result = await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "db": "connected",
        "result": result.scalar(),
    }