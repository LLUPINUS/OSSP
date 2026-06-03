import asyncio
import os
import re
import httpx
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


def _duration_to_seconds(iso: str | None) -> int:
    """ISO 8601 길이를 총 초(int)로 변환. 파싱 불가 시 0."""
    if not iso:
        return 0
    m = _DURATION_RE.match(iso)
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


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
        iso = content.get("duration")
        details[item["id"]] = {
            "duration": _format_duration(iso),
            "viewCount": _format_view_count(stats.get("viewCount")),
            "seconds": _duration_to_seconds(iso),
        }
    return details


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


async def _is_shorts(client: httpx.AsyncClient, video_id: str) -> bool:
    """Shorts URL로 HEAD 요청 → 200이면 Shorts, 리다이렉트면 일반 영상."""
    try:
        resp = await client.head(
            f"https://www.youtube.com/shorts/{video_id}",
            follow_redirects=False,
            timeout=3.0,
            headers=_BROWSER_HEADERS,
        )
        print(f"[shorts_check] {video_id} → {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"[shorts_check] {video_id} → 오류: {e}")
        return False


async def search_videos(query: str, target: int = 5, page_token: str | None = None) -> dict:
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        params = dict(
            q=query + " 요리",
            part="snippet",
            type="video",
            maxResults=target * 4,  # 쇼츠 필터링 후 target개 확보를 위해 4배 요청 (5*4=20)
            relevanceLanguage="ko",
        )
        if page_token:
            params["pageToken"] = page_token
        response = youtube.search().list(**params).execute()

        results = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            results.append({
                "videoId": item["id"]["videoId"],
                "title": snippet["title"],
                "thumbnail": snippet["thumbnails"]["medium"]["url"],
                "channelTitle": snippet["channelTitle"],
            })

        # 2차 호출로 길이·조회수 병합
        details = _fetch_details(youtube, [r["videoId"] for r in results])
        for r in results:
            meta = details.get(r["videoId"])
            if meta:
                r["duration"] = meta["duration"]
                r["viewCount"] = meta["viewCount"]

        # Shorts URL HEAD 요청으로 쇼츠 여부 병렬 확인
        async with httpx.AsyncClient() as client:
            shorts_flags = await asyncio.gather(
                *[_is_shorts(client, r["videoId"]) for r in results]
            )

        filtered = [r for r, is_short in zip(results, shorts_flags) if not is_short]

        return {
            "items": filtered[:target],
            "nextPageToken": response.get("nextPageToken"),
        }
    except Exception as e:
        print(f"[youtube_search] 오류: {e}")
        return {"items": [], "nextPageToken": None}
