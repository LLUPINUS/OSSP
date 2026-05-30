import { useVideoStore } from "../store/useVideoStore";
import { searchVideos } from "./api";

// Home 제출 / 결과 화면 재검색 공통 진입점.
// phase를 results로 옮기고(이미 results면 그대로), 로딩→성공/빈결과/에러로 전환한다.
export async function runSearch(query: string): Promise<void> {
  const q = query.trim();
  if (!q) return;

  const s = useVideoStore.getState();
  s.setSearchQuery(q);
  s.setPhase("results");
  s.setSearchStatus("loading");
  s.setSearchResults([]);

  try {
    const results = await searchVideos(q);
    s.setSearchResults(results);
    s.setSearchStatus(results.length > 0 ? "success" : "empty");
  } catch {
    s.setSearchResults([]);
    s.setSearchStatus("error");
  }
}
