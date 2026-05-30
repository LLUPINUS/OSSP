export interface CookingStep {
  action: string;
  start_time: string;
  end_time: string;
  gesture?: string;
}

export interface VideoSearchResult {
  videoId: string;
  title: string;
  thumbnail: string;
  channelTitle: string;
  // 아래는 백엔드 /api/search가 아직 제공하지 않음(README 4.2 — videos.list 2차 호출 필요).
  // UI에서는 있으면 표시, 없으면 생략/placeholder 처리.
  duration?: string; // "12:34"
  viewCount?: string; // "1,234만회"
}

export type PlayerStatus = "idle" | "playing" | "paused";

// 화면 흐름 단계 (Zustand phase 상태머신).
// 시작전 바텀시트는 별도 phase가 아니라 results 위에 뜨는 모달(preCookOpen)로 다룬다.
export type Phase = "home" | "results" | "camera" | "processing" | "sync";

// 검색 결과 화면의 3상태 (+ 에러)
export type SearchStatus = "idle" | "loading" | "success" | "empty" | "error";

// 동기화 재생 화면의 AI 인식 게이트 상태 (README 6. AI 인식 게이트)
export type AiGateState = "waiting" | "analyzing" | "recognized";
