from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable


def get_transcript(video_id: str) -> list[dict]:
    try:
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=["ko", "en"])
        return [{"start": s.start, "duration": s.duration, "text": s.text} for s in fetched]
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        print(f"[transcript] 자막 없음: {e}")
        return []
    except Exception as e:
        print(f"[transcript] 오류: {e}")
        return []


def format_for_gemini(transcript: list[dict]) -> str:
    lines = []
    for entry in transcript:
        start = int(entry["start"])
        minutes, seconds = divmod(start, 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {entry['text']}")
    return "\n".join(lines)
