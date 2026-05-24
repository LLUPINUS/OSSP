"""
SQLAlchemy 엔진과 세션 설정.

FastAPI 엔드포인트에서 DB에 접근할 때 쓰는 객체들을 정의한다.
- engine: 앱 전체에서 공유하는 비동기 연결 풀
- AsyncSessionLocal: 요청마다 새로 만들어 쓰는 세션 팩토리
- Base: DB 모델(테이블) 클래스가 상속할 부모 클래스
- get_db: FastAPI 의존성 주입용 세션 제공 함수
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# === 비동기 엔진 ===
# DATABASE_URL의 드라이버 부분이 `postgresql+asyncpg`여야 한다.
# echo=settings.DEBUG: True면 실행되는 모든 SQL을 콘솔에 출력 (디버깅용).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)


# === 세션 팩토리 ===
# 호출할 때마다 새 AsyncSession 인스턴스를 만들어주는 "공장".
# expire_on_commit=False: commit 후에도 객체 속성에 접근 가능하게 함 (FastAPI 응답 직렬화 시 필요).
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# === Declarative Base ===
# 앞으로 만들 모든 DB 모델 클래스가 이걸 상속한다.
# 예: class Recipe(Base): __tablename__ = "recipes" ...
class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 부모."""
    pass


# === FastAPI 의존성: 요청마다 DB 세션 제공 ===
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 엔드포인트에서 `Depends(get_db)`로 받아 쓴다.

    요청이 시작될 때 세션을 만들고, 끝날 때 자동으로 닫는다.
    엔드포인트 안에서 예외가 발생해도 세션은 안전하게 정리된다.
    """
    async with AsyncSessionLocal() as session:
        yield session