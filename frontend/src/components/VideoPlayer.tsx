import { useRef, useCallback } from "react";
import YouTube, { type YouTubePlayer, type YouTubeEvent } from "react-youtube";
import { useVideoStore } from "../store/useVideoStore";

const OPTS = {
  height: "390",
  width: "640",
  playerVars: { autoplay: 0 as const },
};

export default function VideoPlayer() {
  const playerRef = useRef<YouTubePlayer | null>(null);
  const selectedVideo = useVideoStore((s) => s.selectedVideo);
  const playerStatus = useVideoStore((s) => s.playerStatus);
  const setPlayerStatus = useVideoStore((s) => s.setPlayerStatus);

  const onReady = useCallback((e: YouTubeEvent) => {
    playerRef.current = e.target;
    setPlayerStatus("paused");
  }, [setPlayerStatus]);

  const onPlay = useCallback(() => setPlayerStatus("playing"), [setPlayerStatus]);
  const onPause = useCallback(() => setPlayerStatus("paused"), [setPlayerStatus]);

  if (!selectedVideo) {
    return (
      <div className="flex items-center justify-center w-[640px] h-[390px] bg-gray-100 rounded text-gray-400 text-sm">
        영상을 검색하여 선택해주세요
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <YouTube
        videoId={selectedVideo.videoId}
        opts={OPTS}
        onReady={onReady}
        onPlay={onPlay}
        onPause={onPause}
      />
      <p className="text-xs text-gray-500">상태: {playerStatus}</p>
    </div>
  );
}

export function usePlayerControls() {
  const playerRef = useRef<YouTubePlayer | null>(null);

  const play = useCallback(() => playerRef.current?.playVideo(), []);
  const pause = useCallback(() => playerRef.current?.pauseVideo(), []);
  const seekTo = useCallback((seconds: number) => {
    playerRef.current?.seekTo(seconds, true);
  }, []);

  return { playerRef, play, pause, seekTo };
}
