import os
import re
from googleapiclient.discovery import build

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# ISO 8601 길이 표기(PT1H2M3S 등) 파서
_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _format_duration(iso: str | None) -> str | None:
    """ISO 8601 길이(PT12M34S)를 'M:SS' / 'H:MM:SS'로 변환. 파싱 불가 시 None."""
    if not iso:
        return None
    m = _DURATION_RE.match(iso)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _format_view_count(raw: str | None) -> str | None:
    """조회수 문자열을 한국어 축약('1.2만회'/'12만회'/'1.2억회'/'1,234회')으로. 숫자 아니면 None."""
    if raw is None or not str(raw).isdigit():
        return None
    n = int(raw)
    if n >= 100_000_000:  # 억 단위
        s = f"{n / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}억회"
    if n >= 10_000:  # 만 단위
        man = n / 10_000
        if man >= 10:  # 10만 이상은 정수 만 (12만회, 1,234만회)
            return f"{int(man):,}만회"
        s = f"{man:.1f}".rstrip("0").rstrip(".")  # 1만~9.9만은 소수 1자리 (1.2만회, 1만회)
        return f"{s}만회"
    return f"{n:,}회"


def _fetch_details(youtube, video_ids: list[str]) -> dict[str, dict]:
    """videos.list 2차 호출로 영상별 길이·조회수를 가져온다.

    search.list(snippet)에는 길이·조회수가 없어 별도 호출이 필요하다.
    best-effort: 실패하면 빈 dict를 돌려줘 검색 결과 자체는 살린다.
    """
    if not video_ids:
        return {}
    try:
        response = youtube.videos().list(
            part="contentDetails,statistics",
            id=",".join(video_ids),
        ).execute()
    except Exception as e:
        print(f"[youtube_search] videos.list 실패 (길이·조회수 생략): {e}")
        return {}

    details: dict[str, dict] = {}
    for item in response.get("items", []):
        content = item.get("contentDetails", {})
        stats = item.get("statistics", {})
        details[item["id"]] = {
            "duration": _format_duration(content.get("duration")),
            "viewCount": _format_view_count(stats.get("viewCount")),
        }
    return details


def search_videos(query: str, max_results: int = 15) -> list[dict]:
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=query + " 요리",
            part="snippet",
            type="video",
            maxResults=max_results,
            relevanceLanguage="ko",
        )
        response = request.execute()

        results = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            results.append({
                "videoId": item["id"]["videoId"],
                "title": snippet["title"],
                "thumbnail": snippet["thumbnails"]["medium"]["url"],
                "channelTitle": snippet["channelTitle"],
            })

        # 2차 호출로 길이·조회수 병합 (videos.list=1 unit, best-effort)
        details = _fetch_details(youtube, [r["videoId"] for r in results])
        for r in results:
            meta = details.get(r["videoId"])
            if meta:
                r["duration"] = meta["duration"]
                r["viewCount"] = meta["viewCount"]

        return results
    except Exception as e:
        print(f"[youtube_search] 오류: {e}")
        return []
