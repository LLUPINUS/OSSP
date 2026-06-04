import { useRef, useState } from "react";
import { useVideoStore } from "../../store/useVideoStore";
import { runSearch, loadMore } from "../../lib/search";
import { useSuggest } from "../../hooks/useSuggest";
import type { VideoSearchResult } from "../../types";
import SuggestList from "../SuggestList";
import { BackIcon, SearchIcon, VideoGlyphIcon, XIcon } from "../icons";
import PreCookSheet from "./PreCookSheet";

export default function ResultsScreen() {
  const searchQuery = useVideoStore((s) => s.searchQuery);
  const searchResults = useVideoStore((s) => s.searchResults);
  const searchStatus = useVideoStore((s) => s.searchStatus);
  const nextPageToken = useVideoStore((s) => s.nextPageToken);
  const goHome = useVideoStore((s) => s.goHome);
  const setSelectedVideo = useVideoStore((s) => s.setSelectedVideo);
  const setPreCookOpen = useVideoStore((s) => s.setPreCookOpen);

  const [loadingMore, setLoadingMore] = useState(false);

  // 검색창은 편집 가능한 draft. 라벨은 실제 실행된 검색어(searchQuery)를 쓴다.
  const [draft, setDraft] = useState(searchQuery);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = draft.trim().length > 0;
  const { suggestions, open, highlight, onInputKeyDown, select, close, setHighlight } =
    useSuggest(draft, (value) => {
      setDraft(value);
      runSearch(value);
      inputRef.current?.blur();
    });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!hasText) return;
    close();
    runSearch(draft);
    inputRef.current?.blur();
  }

  function handleClear() {
    setDraft("");
    inputRef.current?.focus();
  }

  function openPre(video: VideoSearchResult) {
    setSelectedVideo(video);
    setPreCookOpen(true);
  }

  async function handleLoadMore() {
    setLoadingMore(true);
    await loadMore();
    setLoadingMore(false);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* 상단 네비 */}
      <div className="flex shrink-0 items-center gap-2 border-b border-line px-3.5 pb-3 pt-1">
        <button
          onClick={goHome}
          aria-label="뒤로"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-ink transition-colors active:bg-fill"
        >
          <BackIcon className="h-[22px] w-[22px]" />
        </button>
        <form
          onSubmit={handleSubmit}
          autoComplete="off"
          className="relative flex h-[42px] min-w-0 flex-1 items-center gap-2.5 rounded-[21px] bg-fill px-4"
        >
          <SearchIcon className="h-[18px] w-[18px] shrink-0 text-ink-3" />
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onInputKeyDown}
            onBlur={close}
            enterKeyHint="search"
            className="min-w-0 flex-1 bg-transparent text-[15px] font-semibold tracking-[-0.01em] text-ink outline-none"
          />
          {hasText && (
            <button
              type="button"
              onClick={handleClear}
              aria-label="검색어 지우기"
              className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-ink/[0.07] p-[6px] text-ink-2 transition-colors active:bg-ink/15"
            >
              <XIcon className="h-full w-full" />
            </button>
          )}
          {open && (
            <SuggestList
              items={suggestions}
              highlight={highlight}
              onSelect={select}
              onHover={setHighlight}
              className="absolute left-0 right-0 top-[calc(100%+10px)] z-30"
            />
          )}
        </form>
      </div>

      {/* 메타 줄 (결과 있을 때만) */}
      {searchStatus === "success" && (
        <div className="flex shrink-0 items-center justify-between px-5 pb-[7px] pt-[11px]">
          <span className="min-w-0 truncate text-[12.5px] font-semibold tracking-[-0.01em] text-ink-2">
            ‘{searchQuery}’ 검색결과
          </span>
          <span className="shrink-0 pl-3 text-[11.5px] font-medium text-ink-3">
            {searchResults.length}개
          </span>
        </div>
      )}

      {/* 리스트 영역 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-7 pt-0.5">
        {searchStatus === "loading" && <ResultsSkeleton />}
        {searchStatus === "empty" && <ResultsEmpty query={searchQuery} />}
        {searchStatus === "error" && <ResultsError />}
        {searchStatus === "success" &&
          searchResults.map((v) => (
            <ResultItem key={v.videoId} video={v} onSelect={openPre} />
          ))}
        {searchStatus === "success" && nextPageToken && (
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="mt-1 w-full rounded-[14px] bg-fill py-3.5 text-[14px] font-semibold tracking-[-0.01em] text-ink-2 transition-opacity active:opacity-60 disabled:opacity-40"
          >
            {loadingMore ? "불러오는 중..." : "더 보기"}
          </button>
        )}
      </div>

      {/* 시작 전 바텀시트 (항상 마운트, preCookOpen으로 슬라이드) */}
      <PreCookSheet />
    </div>
  );
}

function ResultItem({
  video,
  onSelect,
}: {
  video: VideoSearchResult;
  onSelect: (v: VideoSearchResult) => void;
}) {
  return (
    <div
      onClick={() => onSelect(video)}
      className="flex cursor-pointer gap-3 py-[11px] active:opacity-90"
    >
      <div className="relative h-[78px] w-[132px] shrink-0 overflow-hidden rounded-[13px] bg-gradient-to-br from-[#f1efec] to-[#e7e4df]">
        {video.thumbnail ? (
          <img
            src={video.thumbnail}
            alt={video.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[#c9c4bc]">
            <VideoGlyphIcon className="h-[26px] w-[26px]" />
          </div>
        )}
        {video.duration && (
          <span className="absolute bottom-1.5 right-1.5 rounded-[5px] bg-black/[0.78] px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-white">
            {video.duration}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1 pt-px">
        <div className="line-clamp-2 text-[14.5px] font-semibold leading-snug tracking-[-0.01em] text-ink">
          {video.title}
        </div>
        <div className="mt-[7px] truncate text-[12.5px] font-medium tracking-[-0.01em] text-ink-3">
          {video.channelTitle}
          {video.viewCount ? ` · 조회수 ${video.viewCount}` : ""}
        </div>
      </div>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex animate-pulse gap-3 py-[11px]">
          <div className="h-[78px] w-[132px] shrink-0 rounded-[13px] bg-fill" />
          <div className="flex-1 pt-[3px]">
            <div className="h-[11px] w-[92%] rounded-[5px] bg-fill" />
            <div className="mt-[9px] h-[11px] w-[74%] rounded-[5px] bg-fill" />
            <div className="mt-[9px] h-[11px] w-[44%] rounded-[5px] bg-fill" />
          </div>
        </div>
      ))}
    </>
  );
}

function ResultsEmpty({ query }: { query: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3.5 px-9 pb-[60px] pt-24 text-center">
      <div className="flex h-[60px] w-[60px] items-center justify-center rounded-full bg-fill text-ink-3">
        <SearchIcon className="h-7 w-7" />
      </div>
      <div className="text-base font-bold tracking-[-0.01em] text-ink">
        검색 결과가 없어요
      </div>
      <div className="text-[13px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
        ‘{query}’에 대한 영상을 찾지 못했어요.
        <br />
        다른 검색어로 다시 시도해보세요.
      </div>
    </div>
  );
}

function ResultsError() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3.5 px-9 pb-[60px] pt-24 text-center">
      <div className="flex h-[60px] w-[60px] items-center justify-center rounded-full bg-fill text-ink-3">
        <SearchIcon className="h-7 w-7" />
      </div>
      <div className="text-base font-bold tracking-[-0.01em] text-ink">
        검색 중 문제가 발생했어요
      </div>
      <div className="text-[13px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
        잠시 후 다시 시도해주세요.
      </div>
    </div>
  );
}
