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
  // 이미 '실행된' 검색어 — 그 값이 입력창에 그대로 남아도 자동완성을 다시 띄우지 않는다.
  // 초기 query(결과 화면에 들고 들어온 검색어)도 실행된 것으로 간주해 마운트 시 자동 오픈을 막는다.
  const skipRef = useRef<string | null>(query.trim() || null);

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
      // 취소됐거나, 그 사이 제출/선택돼 실행된 검색어가 됐으면 무시 (늦은 응답이 드롭다운을 다시 열지 않게)
      if (ctrl.signal.aborted || q === skipRef.current) return;
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

  // 검색을 '실행'했음을 기록 (제출·선택 공통). 이후 같은 값이 입력창에 남아도 재오픈하지 않는다.
  function commit(value: string) {
    skipRef.current = value.trim();
    close();
  }

  function select(value: string) {
    commit(value); // 선택 결과가 query에 반영돼도 재오픈 방지
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

  return { suggestions, open, highlight, onInputKeyDown, select, commit, close, setHighlight };
}
