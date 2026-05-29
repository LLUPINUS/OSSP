import { useState, useEffect, useRef } from "react";
import type { VideoSearchResult } from "../types";
import { useVideoStore } from "../store/useVideoStore";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VideoSearchResult[]>([]);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setSelectedVideo = useVideoStore((s) => s.setSelectedVideo);
  const setCookingSteps = useVideoStore((s) => s.setCookingSteps);

  useEffect(() => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(query)}`);
        if (res.ok) setSuggestions(await res.json());
      } catch {}
    }, 300);
    return () => {
      if (suggestTimer.current) clearTimeout(suggestTimer.current);
    };
  }, [query]);

  async function fetchSearch(q: string, token?: string | null) {
    const url = token
      ? `/api/search?q=${encodeURIComponent(q)}&pageToken=${token}`
      : `/api/search?q=${encodeURIComponent(q)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("검색 실패");
    return res.json() as Promise<{ items: VideoSearchResult[]; nextPageToken: string | null }>;
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setShowSuggestions(false);
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSearch(query);
      setResults(data.items);
      setNextPageToken(data.nextPageToken ?? null);
    } catch {
      setError("영상 검색 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSuggestionClick(s: string) {
    setQuery(s);
    setShowSuggestions(false);
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSearch(s);
      setResults(data.items);
      setNextPageToken(data.nextPageToken ?? null);
    } catch {
      setError("영상 검색 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadMore() {
    if (!nextPageToken) return;
    setLoadingMore(true);
    try {
      const data = await fetchSearch(query, nextPageToken);
      setResults((prev) => [...prev, ...data.items]);
      setNextPageToken(data.nextPageToken ?? null);
    } catch {
      setError("추가 영상 로드 중 오류가 발생했습니다.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleSelect(video: VideoSearchResult) {
    setSelectedVideo(video);
    setCookingSteps([]);
    setError(null);
    setShowSuggestions(false);
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
        <div className="flex-1 relative">
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setShowSuggestions(true); }}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="요리 이름 검색 (예: 감자볶음)"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute left-0 right-0 top-full mt-1 bg-white border rounded shadow-lg z-10">
              {suggestions.map((s, i) => (
                <li
                  key={i}
                  onMouseDown={() => handleSuggestionClick(s)}
                  className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-100"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
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

      {nextPageToken && (
        <button
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="mt-3 w-full py-2 text-sm border rounded hover:bg-gray-50 disabled:opacity-50"
        >
          {loadingMore ? "불러오는 중..." : "더 보기"}
        </button>
      )}
    </div>
  );
}
