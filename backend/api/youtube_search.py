import os
from googleapiclient.discovery import build

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")


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
        return results
    except Exception as e:
        print(f"[youtube_search] 오류: {e}")
        return []
