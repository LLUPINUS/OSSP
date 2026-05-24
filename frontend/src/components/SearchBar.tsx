import { useState } from "react";
import type { VideoSearchResult } from "../types";
import { useVideoStore } from "../store/useVideoStore";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VideoSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setSelectedVideo = useVideoStore((s) => s.setSelectedVideo);
  const setCookingSteps = useVideoStore((s) => s.setCookingSteps);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error("검색 실패");
      const data: VideoSearchResult[] = await res.json();
      setResults(data);
    } catch (err) {
      setError("영상 검색 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(video: VideoSearchResult) {
    setSelectedVideo(video);
    setCookingSteps([]);
    setError(null);
    try {
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
      const steps = await res.json();
      setCookingSteps(steps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "요리 단계 로드 중 오류가 발생했습니다.");
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto p-4">
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="요리 이름 검색 (예: 감자볶음)"
          className="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded text-sm hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? "검색 중..." : "검색"}
        </button>
      </form>

      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}

      <ul className="mt-3 space-y-2 max-h-96 overflow-y-auto">
        {results.map((v) => (
          <li
            key={v.videoId}
            onClick={() => handleSelect(v)}
            className="flex items-center gap-3 p-2 border rounded cursor-pointer hover:bg-gray-50"
          >
            <img src={v.thumbnail} alt={v.title} className="w-24 h-14 object-cover rounded" />
            <div className="text-left">
              <p className="text-sm font-medium line-clamp-2">{v.title}</p>
              <p className="text-xs text-gray-500">{v.channelTitle}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
