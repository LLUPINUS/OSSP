import { useVideoStore } from "../store/useVideoStore";
import { searchVideos } from "./api";

export async function runSearch(query: string): Promise<void> {
  const q = query.trim();
  if (!q) return;

  const s = useVideoStore.getState();
  s.setSearchQuery(q);
  s.setPhase("results");
  s.setSearchStatus("loading");
  s.setSearchResults([]);
  s.setNextPageToken(null);

  try {
    const data = await searchVideos(q);
    s.setSearchResults(data.items);
    s.setNextPageToken(data.nextPageToken);
    s.setSearchStatus(data.items.length > 0 ? "success" : "empty");
  } catch {
    s.setSearchResults([]);
    s.setNextPageToken(null);
    s.setSearchStatus("error");
  }
}

export async function loadMore(): Promise<void> {
  const s = useVideoStore.getState();
  const { searchQuery, nextPageToken } = s;
  if (!nextPageToken) return;

  try {
    const data = await searchVideos(searchQuery, nextPageToken);
    s.appendSearchResults(data.items);
    s.setNextPageToken(data.nextPageToken);
  } catch {
    // 더 보기 실패는 조용히 무시 (기존 결과는 유지)
  }
}
