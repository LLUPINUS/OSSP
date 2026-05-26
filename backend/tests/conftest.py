"""
통합 테스트 공통 설정 (fixtures).

전용 PostgreSQL 테스트 DB(.env의 TEST_DATABASE_URL)에 대해
매 테스트마다 스키마를 새로 만들고(create_all) 끝나면 지운다(drop_all).
서비스 함수들이 내부에서 commit을 호출하므로, 트랜잭션 롤백 대신
테이블 생성/삭제로 테스트 간 격리를 보장한다.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401  # Base.metadata에 4개 테이블 등록
from app.models.action_label import ActionLabel

# TEST_DATABASE_URL이 없으면 이 디렉토리의 모든 테스트를 skip한다.
requires_test_db = pytest.mark.skipif(
    not settings.TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL이 .env에 설정되지 않음",
)

# CLAUDE.md 확정 행동 라벨 4종 (시드)
ACTION_LABELS = [
    ("cutting", "썰기"),
    ("grilling", "굽기"),
    ("stir_frying", "볶기"),
    ("stirring", "젓기"),
]


@pytest_asyncio.fixture
async def engine():
    """테스트 DB에 스키마를 만들고, 테스트가 끝나면 모두 지운다."""
    eng = create_async_engine(settings.TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """action_labels 4종이 시드된 세션을 제공한다."""
    maker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with maker() as s:
        for name, ko in ACTION_LABELS:
            s.add(ActionLabel(name=name, display_name_ko=ko))
        await s.commit()
        yield s
