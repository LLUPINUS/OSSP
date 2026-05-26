"""
db_service.py DB 레이어 통합 테스트.

검증 대상: Recipe → Transcript → CookingStep 흐름의 정합성과
캐싱/멱등성/라벨 매칭 같은 "조용히 깨질 수 있는" 지점들.
"""

import pytest
from sqlalchemy import func, select

from api.db_service import (
    get_cached_recipe,
    get_cached_steps,
    get_or_create_recipe,
    mark_completed,
    mark_processing,
    save_cooking_steps,
    save_transcripts,
)
from app.core.config import settings
from app.models.cooking_step import CookingStep
from app.models.recipe import Recipe
from app.models.transcript import Transcript

# TEST_DATABASE_URL이 없으면 이 파일 전체를 skip.
pytestmark = pytest.mark.skipif(
    not settings.TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL이 .env에 설정되지 않음",
)

STEPS = [
    {"action": "감자 썰기", "start_time": "00:10", "end_time": "00:30", "gesture": "썰기"},
    {"action": "양파 볶기", "start_time": "01:00", "end_time": "01:40", "gesture": "볶기"},
]

TRANSCRIPT = [
    {"start": 10.0, "duration": 5.0, "text": "감자를 썬다"},
    {"start": 60.0, "duration": 8.0, "text": "양파를 볶는다"},
]


async def test_get_or_create_recipe_idempotent(session):
    """같은 video_id로 두 번 호출해도 새 recipe가 생기지 않는다."""
    r1 = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()
    r2 = await get_or_create_recipe(session, "vid1", "다른 제목")

    assert r1.id == r2.id
    count = await session.scalar(select(func.count()).select_from(Recipe))
    assert count == 1


async def test_save_transcripts_idempotent(session):
    """transcript를 두 번 저장해도 중복이 쌓이지 않는다 (delete 후 재삽입)."""
    r = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()

    n1 = await save_transcripts(session, r.id, TRANSCRIPT)
    n2 = await save_transcripts(session, r.id, TRANSCRIPT)

    assert n1 == n2 == 2
    count = await session.scalar(select(func.count()).select_from(Transcript))
    assert count == 2


async def test_save_cooking_steps_resolves_action_label(session):
    """한글 gesture가 시드된 action_label로 매칭되고, 미지의 gesture는 건너뛴다."""
    r = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()

    steps = STEPS + [
        {"action": "플레이팅", "start_time": "02:00", "end_time": "02:10", "gesture": "담기"},
    ]
    saved = await save_cooking_steps(session, r.id, steps)

    # "담기"는 시드에 없으므로 저장에서 제외 → 2건만 저장
    assert saved == 2
    rows = (
        await session.execute(
            select(CookingStep).where(CookingStep.recipe_id == r.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert all(row.action_label_id is not None for row in rows)


async def test_save_cooking_steps_idempotent(session):
    """cooking_steps도 재호출 시 기존 데이터를 덮어쓴다."""
    r = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()

    await save_cooking_steps(session, r.id, STEPS)
    await save_cooking_steps(session, r.id, STEPS)

    count = await session.scalar(
        select(func.count()).select_from(CookingStep)
    )
    assert count == 2


async def test_get_cached_recipe_only_completed(session):
    """COMPLETED 상태의 recipe만 캐시로 반환된다."""
    r = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()

    assert await get_cached_recipe(session, "vid1") is None  # PENDING

    await mark_processing(session, r.id)
    assert await get_cached_recipe(session, "vid1") is None  # PROCESSING

    await mark_completed(session, r.id)
    cached = await get_cached_recipe(session, "vid1")
    assert cached is not None and cached.id == r.id


async def test_get_cached_steps_roundtrip(session):
    """저장된 steps가 초→'MM:SS' + display_name_ko 형태로, 순서대로 복원된다."""
    r = await get_or_create_recipe(session, "vid1", "제목")
    await session.commit()
    await save_cooking_steps(session, r.id, STEPS)

    cached = await get_cached_steps(session, r.id)
    assert cached == [
        {"action": "감자 썰기", "start_time": "00:10", "end_time": "00:30", "gesture": "썰기"},
        {"action": "양파 볶기", "start_time": "01:00", "end_time": "01:40", "gesture": "볶기"},
    ]


async def test_full_flow(session):
    """recipe → transcript → steps → completed → 캐시 조회까지 일관성 확인."""
    r = await get_or_create_recipe(
        session, "vid1", "김치찌개",
        channel_name="요리채널", thumbnail_url="http://img",
    )
    await session.commit()

    await mark_processing(session, r.id)
    n_tx = await save_transcripts(session, r.id, TRANSCRIPT)
    n_steps = await save_cooking_steps(session, r.id, STEPS)
    await mark_completed(session, r.id)

    assert n_tx == 2 and n_steps == 2

    cached_recipe = await get_cached_recipe(session, "vid1")
    assert cached_recipe is not None

    cached_steps = await get_cached_steps(session, cached_recipe.id)
    assert len(cached_steps) == 2
    assert cached_steps[0]["gesture"] == "썰기"
