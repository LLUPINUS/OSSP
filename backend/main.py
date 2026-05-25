from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from api.youtube_search import search_videos
from api.transcript import get_transcript, format_for_gemini
from api.gemini_parser import parse_cooking_steps

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


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    try:
        results = search_videos(q)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/steps")
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

    steps = parse_cooking_steps(format_for_gemini(transcript))

    # 허용된 제스처에 해당하는 단계만 유지
    from api.gemini_parser import GESTURES
    steps = [s for s in steps if s.get("gesture") in set(GESTURES)]

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
