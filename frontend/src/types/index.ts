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
}

export type PlayerStatus = "idle" | "playing" | "paused";
