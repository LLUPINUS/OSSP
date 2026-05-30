import type { CookingStep, VideoSearchResult } from "../types";

// 백엔드 API 계약 (기존 SearchBar에서 검증된 호출을 공통화).
// Vite dev 프록시가 /api → http://localhost:8000 로 전달.

export async function searchVideos(query: string): Promise<VideoSearchResult[]> {
  const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error("검색 실패");
  return res.json();
}

export async function fetchCookingSteps(
  video: VideoSearchResult
): Promise<CookingStep[]> {
  const params = new URLSearchParams({
    videoId: video.videoId,
    title: video.title,
    channelTitle: video.channelTitle,
    thumbnail: video.thumbnail,
  });
  const res = await fetch(`/api/steps?${params}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? "단계 로드 실패");
  }
  return res.json();
}
