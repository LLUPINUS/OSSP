import { useEffect, useRef, useState } from "react";
import { fetchSuggestions } from "../lib/api";

const DEBOUNCE_MS = 250;

// 검색창 자동완성 로직 (Home·Results 공용).
// query가 바뀌면 debounce 후 /api/suggest를 호출하고(이전 요청은 취소),
// 드롭다운 열림/하이라이트 상태와 키보드 핸들러를 함께 돌려준다.
// onSelect: 항목을 고르거나 Enter로 확정했을 때 호출 (보통 입력값 반영 + 검색 실행).
export function useSuggest(query: string, onSelect: (value: string) => void) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  // 방금 선택/확정한 검색어 — 그 값이 입력창에 반영돼도 자동완성을 다시 띄우지 않는다.
  const skipRef = useRef<string | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (!q || q === skipRef.current) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      const list = await fetchSuggestions(q, ctrl.signal);
      if (ctrl.signal.aborted) return; // 다음 입력으로 취소된 stale 응답은 무시
      setSuggestions(list);
      setOpen(list.length > 0);
      setHighlight(-1);
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [query]);

  function close() {
    setOpen(false);
    setHighlight(-1);
  }

  function select(value: string) {
    skipRef.current = value; // 선택 결과가 query에 반영돼도 재오픈 방지
    close();
    onSelect(value);
  }

  function onInputKeyDown(e: React.KeyboardEvent) {
    if (!open || suggestions.length === 0) return;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setHighlight((i) => (i + 1) % suggestions.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setHighlight((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
        break;
      case "Enter":
        if (highlight >= 0) {
          e.preventDefault(); // 폼 제출 대신 하이라이트된 항목 선택
          select(suggestions[highlight]);
        } else {
          close(); // 입력 그대로 제출 → 드롭다운만 닫음
        }
        break;
      case "Escape":
        close();
        break;
    }
  }

  return { suggestions, open, highlight, onInputKeyDown, select, close, setHighlight };
}
