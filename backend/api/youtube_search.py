import os
from googleapiclient.discovery import build

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")


def search_videos(query: str, max_results: int = 15, page_token: str | None = None) -> dict:
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        params = dict(
            q=query + " 요리",
            part="snippet",
            type="video",
            maxResults=max_results,
            relevanceLanguage="ko",
        )
        if page_token:
            params["pageToken"] = page_token
        response = youtube.search().list(**params).execute()
        items = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            items.append({
                "videoId": item["id"]["videoId"],
                "title": snippet["title"],
                "thumbnail": snippet["thumbnails"]["medium"]["url"],
                "channelTitle": snippet["channelTitle"],
            })
        return {
            "items": items,
            "nextPageToken": response.get("nextPageToken"),
        }
    except Exception as e:
        print(f"[youtube_search] 오류: {e}")
        return {"items": [], "nextPageToken": None}
