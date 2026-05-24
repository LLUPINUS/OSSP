import { create } from "zustand";
import type { CookingStep, PlayerStatus, VideoSearchResult } from "../types";

interface VideoState {
  selectedVideo: VideoSearchResult | null;
  cookingSteps: CookingStep[];
  currentStepIndex: number;
  playerStatus: PlayerStatus;
  isActionDetected: boolean;

  setSelectedVideo: (video: VideoSearchResult | null) => void;
  setCookingSteps: (steps: CookingStep[]) => void;
  setCurrentStepIndex: (index: number) => void;
  setPlayerStatus: (status: PlayerStatus) => void;
  setIsActionDetected: (detected: boolean) => void;
}

export const useVideoStore = create<VideoState>((set) => ({
  selectedVideo: null,
  cookingSteps: [],
  currentStepIndex: 0,
  playerStatus: "idle",
  isActionDetected: false,

  setSelectedVideo: (video) => set({ selectedVideo: video }),
  setCookingSteps: (steps) => set({ cookingSteps: steps }),
  setCurrentStepIndex: (index) => set({ currentStepIndex: index }),
  setPlayerStatus: (status) => set({ playerStatus: status }),
  setIsActionDetected: (detected) => set({ isActionDetected: detected }),
}));
