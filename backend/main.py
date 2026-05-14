from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.youtube_search import search_videos
from api.transcript import get_transcript, format_for_gemini
from api.gemini_parser import parse_cooking_steps

app = FastAPI(title="CV 요리 영상 제어 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    try:
        results = search_videos(q)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/steps")
def get_steps(videoId: str = Query(...)):
    try:
        transcript = get_transcript(videoId)
        if not transcript:
            raise HTTPException(status_code=404, detail="자막을 찾을 수 없습니다.")
        text = format_for_gemini(transcript)
        steps = parse_cooking_steps(text)
        return steps
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
