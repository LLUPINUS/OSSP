import type { CookingStep, VideoSearchResult } from "../types";

// 백엔드 API 계약 (기존 SearchBar에서 검증된 호출을 공통화).
// Vite dev 프록시가 /api → http://localhost:8000 로 전달.

export async function searchVideos(
  query: string,
  pageToken?: string,
): Promise<{ items: VideoSearchResult[]; nextPageToken: string | null }> {
  const url = pageToken
    ? `/api/search?q=${encodeURIComponent(query)}&pageToken=${pageToken}`
    : `/api/search?q=${encodeURIComponent(query)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("검색 실패");
  return res.json();
}

// 검색어 자동완성. 백엔드 /api/suggest(Google suggestqueries 프록시)에서 추천어 목록을 받는다.
// 자동완성은 부가 기능이라 실패(네트워크/abort/4xx)는 빈 배열로 흡수하고 검색 흐름을 막지 않는다.
export async function fetchSuggestions(
  query: string,
  signal?: AbortSignal
): Promise<string[]> {
  const q = query.trim();
  if (!q) return [];
  try {
    const res = await fetch(`/api/suggest?q=${encodeURIComponent(q)}`, { signal });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
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
