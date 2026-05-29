from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.recipe import Recipe, ProcessingStatus
from app.models.cooking_step import CookingStep
from app.models.action_label import ActionLabel
from app.models.transcript import Transcript


def _mm_ss_to_seconds(t: str) -> float:
    m, s = t.split(":")
    return float(int(m) * 60 + int(s))


async def get_or_create_recipe(
    session: AsyncSession,
    video_id: str,
    title: str,
    channel_name: str | None = None,
    thumbnail_url: str | None = None,
) -> Recipe:
    result = await session.execute(
        select(Recipe).where(Recipe.youtube_video_id == video_id)
    )
    recipe = result.scalar_one_or_none()
    if recipe:
        return recipe

    recipe = Recipe(
        youtube_video_id=video_id,
        title=title,
        channel_name=channel_name,
        thumbnail_url=thumbnail_url,
        processing_status=ProcessingStatus.PENDING,
    )
    session.add(recipe)
    await session.flush()
    return recipe


async def _resolve_action_label_id(session: AsyncSession, gesture_ko: str) -> int | None:
    result = await session.execute(
        select(ActionLabel).where(ActionLabel.display_name_ko == gesture_ko)
    )
    label = result.scalar_one_or_none()
    return label.id if label else None


async def save_transcript(
    session: AsyncSession,
    recipe_id: int,
    transcript: list[dict],
) -> int:
    """원본 자막 전체를 transcripts 테이블에 저장한다. 재호출 시 기존 데이터를 덮어쓴다."""
    await session.execute(
        delete(Transcript).where(Transcript.recipe_id == recipe_id)
    )
    for entry in transcript:
        session.add(Transcript(
            recipe_id=recipe_id,
            start_time=float(entry["start"]),
            duration=float(entry["duration"]),
            text=entry["text"],
        ))
    await session.commit()
    return len(transcript)


async def save_cooking_steps(
    session: AsyncSession,
    recipe_id: int,
    steps: list[dict],
) -> int:
    """steps를 DB에 저장하고 저장된 개수를 반환한다. 재호출 시 기존 데이터를 덮어쓴다."""
    await session.execute(
        delete(CookingStep).where(CookingStep.recipe_id == recipe_id)
    )

    # action 문자열 기준 중복 제거 — 먼저 나온 단계만 유지
    seen: set[str] = set()
    deduped = []
    for step in steps:
        action = step.get("action", "")
        if action not in seen:
            seen.add(action)
            deduped.append(step)
    steps = deduped

    saved = 0
    for order, step in enumerate(steps, start=1):
        gesture = step.get("gesture")
        if not gesture:
            continue

        action_label_id = await _resolve_action_label_id(session, gesture)
        if action_label_id is None:
            print(f"[db_service] action_label 없음: '{gesture}' — 저장 건너뜀")
            continue

        session.add(CookingStep(
            recipe_id=recipe_id,
            action_label_id=action_label_id,
            step_order=order,
            start_time=_mm_ss_to_seconds(step["start_time"]),
            end_time=_mm_ss_to_seconds(step["end_time"]),
            description=step.get("action"),
        ))
        saved += 1

    await session.commit()
    return saved
