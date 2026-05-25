from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from app.models.recipe import Recipe, ProcessingStatus
from app.models.cooking_step import CookingStep
from app.models.action_label import ActionLabel
from app.models.transcript import Transcript


def _mm_ss_to_seconds(t: str) -> float:
    m, s = t.split(":")
    return float(int(m) * 60 + int(s))


def _seconds_to_mm_ss(sec: float) -> str:
    """330.0 → '05:30'. _mm_ss_to_seconds의 역변환 (캐시 응답 직렬화용)."""
    total = int(sec)
    return f"{total // 60:02d}:{total % 60:02d}"


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


async def save_cooking_steps(
    session: AsyncSession,
    recipe_id: int,
    steps: list[dict],
) -> int:
    """steps를 DB에 저장하고 저장된 개수를 반환한다. 재호출 시 기존 데이터를 덮어쓴다."""
    await session.execute(
        delete(CookingStep).where(CookingStep.recipe_id == recipe_id)
    )

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


# ─────────────────────────────────────────────────────────────────────────────
# DB 캐싱 / 상태 머신 / transcript 적재 (Issue #15)
# ─────────────────────────────────────────────────────────────────────────────

async def get_cached_recipe(session: AsyncSession, video_id: str) -> Recipe | None:
    """처리 완료(COMPLETED)된 recipe만 반환한다. 캐시 미스면 None."""
    result = await session.execute(
        select(Recipe).where(
            Recipe.youtube_video_id == video_id,
            Recipe.processing_status == ProcessingStatus.COMPLETED,
        )
    )
    return result.scalar_one_or_none()


async def get_cached_steps(session: AsyncSession, recipe_id: int) -> list[dict]:
    """저장된 cooking_steps를 Gemini 출력과 동일한 shape으로 복원한다."""
    result = await session.execute(
        select(CookingStep, ActionLabel)
        .join(ActionLabel, CookingStep.action_label_id == ActionLabel.id)
        .where(CookingStep.recipe_id == recipe_id)
        .order_by(CookingStep.step_order)
    )
    return [
        {
            "action": cs.description,
            "start_time": _seconds_to_mm_ss(cs.start_time),
            "end_time": _seconds_to_mm_ss(cs.end_time),
            "gesture": al.display_name_ko,
        }
        for cs, al in result.all()
    ]


async def save_transcripts(
    session: AsyncSession,
    recipe_id: int,
    transcript: list[dict],
) -> int:
    """자막 줄들을 DB에 저장하고 저장된 개수를 반환한다. 재호출 시 기존 행을 덮어쓴다."""
    await session.execute(
        delete(Transcript).where(Transcript.recipe_id == recipe_id)
    )
    for entry in transcript:
        session.add(Transcript(
            recipe_id=recipe_id,
            start_time=entry["start"],
            duration=entry["duration"],
            text=entry["text"],
        ))
    await session.commit()
    return len(transcript)


async def _set_status(
    session: AsyncSession,
    recipe_id: int,
    status: ProcessingStatus,
) -> None:
    await session.execute(
        update(Recipe).where(Recipe.id == recipe_id).values(processing_status=status)
    )
    await session.commit()


async def mark_processing(session: AsyncSession, recipe_id: int) -> None:
    await _set_status(session, recipe_id, ProcessingStatus.PROCESSING)


async def mark_completed(session: AsyncSession, recipe_id: int) -> None:
    await _set_status(session, recipe_id, ProcessingStatus.COMPLETED)


async def mark_failed(session: AsyncSession, recipe_id: int) -> None:
    await _set_status(session, recipe_id, ProcessingStatus.FAILED)
