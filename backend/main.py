from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from api.youtube_search import search_videos
from api.transcript import get_transcript, format_for_gemini
from api.gemini_parser import parse_cooking_steps

# 팀원 DB 연동 — app/ 디렉토리가 없으면 DB 저장 기능은 비활성화
try:
    from app.core.database import get_db
    from api.db_service import get_or_create_recipe, save_cooking_steps
    DB_ENABLED = True
except ImportError:
    DB_ENABLED = False
    print("[main] DB 모듈 없음 - DB 저장 비활성화")

app = FastAPI(title="CV 요리 영상 제어 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    try:
        transcript = get_transcript(videoId)
        if not transcript:
            raise HTTPException(status_code=404, detail="자막을 찾을 수 없습니다.")

        text = format_for_gemini(transcript)
        steps = parse_cooking_steps(text)

        # 허용된 제스처에 해당하는 단계만 유지
        from api.gemini_parser import GESTURES
        steps = [s for s in steps if s.get("gesture") in set(GESTURES)]

        # DB 저장 (DB가 활성화된 경우만)
        if DB_ENABLED and db is not None:
            try:
                recipe = await get_or_create_recipe(
                    db, videoId, title,
                    channel_name=channelTitle,
                    thumbnail_url=thumbnail,
                )
                saved = await save_cooking_steps(db, recipe.id, steps)
                print(f"[main] DB 저장 완료 — recipe_id={recipe.id}, steps={saved}개")
            except Exception as e:
                print(f"[main] DB 저장 실패 (무시): {e}")

        return steps

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
