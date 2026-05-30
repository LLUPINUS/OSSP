import { useState } from "react";
import { runSearch } from "../../lib/search";
import { ArrowRightIcon, SearchIcon } from "../icons";

export default function HomeScreen() {
  const [query, setQuery] = useState("");
  const hasText = query.trim().length > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!hasText) return;
    runSearch(query);
  }

  return (
    <div className="flex flex-1 flex-col px-7">
      {/* 세로 중앙 정렬 + 살짝 위로 광학 보정 */}
      <div className="flex flex-1 flex-col justify-center pb-[90px]">
        <div className="mb-3.5 text-center">
          <div className="inline-block text-[46px] font-extrabold leading-none tracking-[-0.035em]">
            Cook<span className="text-accent">Sync</span>
          </div>
          <div className="mt-4 text-[15.5px] font-medium leading-relaxed tracking-[-0.01em] text-ink-2">
            만들고 싶은 요리를
            <br />
            검색해 보세요
          </div>
        </div>

        <div className="mt-[34px]">
          <form
            onSubmit={handleSubmit}
            autoComplete="off"
            className={`group flex h-[60px] items-center gap-3 rounded-[18px] border-[1.5px] px-[18px] transition-all duration-150 focus-within:border-accent focus-within:bg-white focus-within:shadow-[0_6px_22px_-8px_rgba(255,90,44,0.5)] ${
              hasText ? "border-ink bg-fill" : "border-transparent bg-fill"
            }`}
          >
            <SearchIcon className="h-[22px] w-[22px] shrink-0 text-ink-3 transition-colors group-focus-within:text-accent-ink" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="요리 검색 · 예: 김치찌개"
              enterKeyHint="search"
              className="min-w-0 flex-1 bg-transparent text-[16.5px] font-medium tracking-[-0.01em] text-ink outline-none placeholder:font-medium placeholder:text-ink-3"
            />
            <button
              type="submit"
              aria-label="검색"
              className={`h-[38px] w-[38px] shrink-0 items-center justify-center rounded-xl bg-ink text-white transition-transform active:scale-90 ${
                hasText ? "flex" : "hidden"
              }`}
            >
              <ArrowRightIcon className="h-[18px] w-[18px]" />
            </button>
          </form>
          <div className="mt-4 px-1.5 text-center text-[13px] leading-relaxed tracking-[-0.01em] text-ink-3">
            영상을 선택하면 요리 단계를
            <br />
            자동으로 분석해 안내해드려요
          </div>
        </div>
      </div>
    </div>
  );
}
