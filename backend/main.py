from dotenv import load_dotenv
load_dotenv()

import json

import httpx
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas import CookingStepOut, VideoSearchOut, SearchPageOut  # noqa: F401
from api.youtube_search import search_videos
from api.transcript import get_transcript, format_for_gemini
from api.gemini_parser import parse_cooking_steps, GeminiParseError

# 팀원 DB 연동 — app/ 디렉토리가 없으면 DB 저장 기능은 비활성화
try:
    from app.core.database import get_db
    from api.db_service import (
        get_or_create_recipe,
        save_cooking_steps,
        get_cached_recipe,
        get_cached_steps,
        save_transcripts,
        mark_processing,
        mark_completed,
        mark_failed,
    )
    DB_ENABLED = True
except ImportError:
    DB_ENABLED = False
    print("[main] DB 모듈 없음 - DB 저장 비활성화")

app = FastAPI(title="CV 요리 영상 제어 API")

# CORS: .env의 CORS_ORIGINS를 콤마 구분으로 파싱
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


# === 헬스체크 ===

@app.get("/")
async def root():
    """앱 자체 헬스체크. 서버 프로세스가 살아있는지 확인."""
    return {
        "service": "CookSync API",
        "status": "ok",
        "debug": settings.DEBUG,
    }


if DB_ENABLED:
    @app.get("/health/db")
    async def health_db(db: AsyncSession = Depends(get_db)):
        """DB 연결 헬스체크. PostgreSQL과 통신이 가능한지 확인."""
        result = await db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "db": "connected",
            "result": result.scalar(),
        }


@app.get("/api/suggest", response_model=list[str])
async def suggest(q: str = Query(..., min_length=1)):
    """검색어 자동완성. Google suggestqueries(비공식)를 프록시해 추천어 목록만 반환한다.
    실패 시 빈 배열 — 자동완성은 부가 기능이라 검색 자체를 막지 않는다."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "q": q, "hl": "ko"},
                timeout=3.0,
            )
            data = json.loads(resp.text)
            return data[1]
    except Exception:
        return []


@app.get("/api/search", response_model=SearchPageOut)
async def search(
    q: str = Query(..., min_length=1),
    pageToken: str = Query(default=None),
):
  
    try:
        return await search_videos(q, page_token=pageToken)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/steps", response_model=list[CookingStepOut])
async def get_steps(
    videoId: str = Query(...),
    title: str = Query(default="제목 없음"),
    channelTitle: str = Query(default=None),
    thumbnail: str = Query(default=None),
    db: AsyncSession = Depends(get_db) if DB_ENABLED else Depends(lambda: None),
):
    # 1. 캐시 적중(COMPLETED): 외부 API 호출 없이 DB에서 응답
    if DB_ENABLED and db is not None:
        try:
            cached_recipe = await get_cached_recipe(db, videoId)
            if cached_recipe:
                cached_steps = await get_cached_steps(db, cached_recipe.id)
                print(f"[main] 캐시 적중 — recipe_id={cached_recipe.id}, steps={len(cached_steps)}개")
                return cached_steps
        except Exception as e:
            print(f"[main] 캐시 조회 실패 (무시): {e}")  # 조회 실패해도 아래 정상 처리로 진행

    # 2. 자막 추출 + Gemini 파싱 (캐시 미스 공통 경로)
    transcript = get_transcript(videoId)
    if not transcript:
        raise HTTPException(status_code=404, detail="자막을 찾을 수 없습니다.")

    try:
        steps = parse_cooking_steps(format_for_gemini(transcript))
    except GeminiParseError as e:
        # AI 분석 실패는 캐시에 남기지 않는다(recipe 생성 전이라 오염 없음). 다음 요청 때 재시도된다. (이슈 #5)
        print(f"[main] Gemini 분석 실패: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI 분석에 일시적으로 실패했습니다. 잠시 후 다시 시도해주세요.",
        ) from e

    # 허용된 제스처에 해당하는 단계만 유지
    from api.gemini_parser import GESTURES
    steps = [s for s in steps if s.get("gesture") in set(GESTURES)]

    # 인접 중복 제거 — 직전 단계와 action이 같을 때만 건너뛴다.
    # Gemini가 같은 단계를 연속으로 중복 출력하는 경우만 제거하고,
    # 영상에서 실제로 떨어져 두 번 나오는 반복 단계는 보존한다.
    deduped: list[dict] = []
    for step in steps:
        action = step.get("action", "")
        if deduped and deduped[-1].get("action", "") == action:
            continue
        deduped.append(step)
    steps = deduped

    # 3. DB 저장 (best-effort: 실패해도 steps는 반환)
    if DB_ENABLED and db is not None:
        recipe = None
        try:
            recipe = await get_or_create_recipe(
                db, videoId, title,
                channel_name=channelTitle,
                thumbnail_url=thumbnail,
            )
            await mark_processing(db, recipe.id)
            saved_tx = await save_transcripts(db, recipe.id, transcript)
            saved = await save_cooking_steps(db, recipe.id, steps)
            await mark_completed(db, recipe.id)
            print(f"[main] 처리 완료 — recipe_id={recipe.id}, steps={saved}개, transcript={saved_tx}줄")
        except Exception as e:
            print(f"[main] DB 저장 실패 (무시): {e}")
            if recipe is not None:
                try:
                    await db.rollback()
                    await mark_failed(db, recipe.id)
                except Exception:
                    pass  # 실패 기록마저 실패하면 조용히 넘어감

    return steps
