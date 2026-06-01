import { SearchIcon } from "./icons";

interface SuggestListProps {
  items: string[];
  highlight: number;
  onSelect: (value: string) => void;
  onHover: (index: number) => void;
  className?: string;
}

// 자동완성 드롭다운 목록 (Home·Results 공용). 위치/래퍼 스타일은 className으로 화면이 제어한다.
// onMouseDown preventDefault: 항목 클릭이 input blur(드롭다운 닫힘)보다 먼저 처리되게 해 클릭 유실 방지.
export default function SuggestList({
  items,
  highlight,
  onSelect,
  onHover,
  className = "",
}: SuggestListProps) {
  if (items.length === 0) return null;
  return (
    <ul
      role="listbox"
      className={`overflow-hidden rounded-2xl border border-line bg-white py-1.5 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.22)] ${className}`}
    >
      {items.map((item, i) => (
        <li key={item} role="option" aria-selected={i === highlight}>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onSelect(item)}
            onMouseEnter={() => onHover(i)}
            className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors ${
              i === highlight ? "bg-fill" : "bg-transparent"
            }`}
          >
            <SearchIcon className="h-[17px] w-[17px] shrink-0 text-ink-3" />
            <span className="min-w-0 flex-1 truncate text-[14.5px] font-medium tracking-[-0.01em] text-ink-2">
              {item}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
