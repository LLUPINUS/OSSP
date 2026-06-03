import { create } from "zustand";
import type {
  AiGateState,
  CookingStep,
  Phase,
  PlayerStatus,
  SearchStatus,
  VideoSearchResult,
} from "../types";

interface VideoState {
  // ── 화면 흐름 ──
  phase: Phase;
  preCookOpen: boolean; // 시작 전 바텀시트(results 위 모달)

  // ── 검색 ──
  searchQuery: string;
  searchResults: VideoSearchResult[];
  searchStatus: SearchStatus;
  nextPageToken: string | null;

  // ── 선택/단계 ──
  selectedVideo: VideoSearchResult | null;
  cookingSteps: CookingStep[];
  currentStepIndex: number;

  // ── 재생/인식 ──
  playerStatus: PlayerStatus;
  isActionDetected: boolean;
  aiGateState: AiGateState;

  // ── actions ──
  setPhase: (phase: Phase) => void;
  setPreCookOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setSearchResults: (results: VideoSearchResult[]) => void;
  appendSearchResults: (results: VideoSearchResult[]) => void;
  setSearchStatus: (status: SearchStatus) => void;
  setNextPageToken: (token: string | null) => void;
  setSelectedVideo: (video: VideoSearchResult | null) => void;
  setCookingSteps: (steps: CookingStep[]) => void;
  setCurrentStepIndex: (index: number) => void;
  setPlayerStatus: (status: PlayerStatus) => void;
  setIsActionDetected: (detected: boolean) => void;
  setAiGateState: (state: AiGateState) => void;

  // 초기화면 복귀 — 검색어/결과를 비워 이전 검색이 잔류하지 않게 한다(README 4.1).
  goHome: () => void;
}

export const useVideoStore = create<VideoState>((set) => ({
  phase: "home",
  preCookOpen: false,

  searchQuery: "",
  searchResults: [],
  searchStatus: "idle",
  nextPageToken: null,

  selectedVideo: null,
  cookingSteps: [],
  currentStepIndex: 0,

  playerStatus: "idle",
  isActionDetected: false,
  aiGateState: "waiting",

  setPhase: (phase) => set({ phase }),
  setPreCookOpen: (preCookOpen) => set({ preCookOpen }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSearchResults: (searchResults) => set({ searchResults }),
  appendSearchResults: (results) => set((s) => ({ searchResults: [...s.searchResults, ...results] })),
  setSearchStatus: (searchStatus) => set({ searchStatus }),
  setNextPageToken: (nextPageToken) => set({ nextPageToken }),
  setSelectedVideo: (selectedVideo) => set({ selectedVideo }),
  setCookingSteps: (cookingSteps) => set({ cookingSteps }),
  setCurrentStepIndex: (currentStepIndex) => set({ currentStepIndex }),
  setPlayerStatus: (playerStatus) => set({ playerStatus }),
  setIsActionDetected: (isActionDetected) => set({ isActionDetected }),
  setAiGateState: (aiGateState) => set({ aiGateState }),

  goHome: () =>
    set({
      phase: "home",
      preCookOpen: false,
      searchQuery: "",
      searchResults: [],
      searchStatus: "idle",
      nextPageToken: null,
    }),
}));
