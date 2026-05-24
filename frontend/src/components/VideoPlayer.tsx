import { useRef, useCallback, useEffect } from "react";
import YouTube, { type YouTubePlayer, type YouTubeEvent } from "react-youtube";
import { useVideoStore } from "../store/useVideoStore";

const OPTS = {
  height: "390",
  width: "640",
  playerVars: { autoplay: 0 as const },
};

function timeToSeconds(t: string): number {
  const [m, s] = t.split(":").map(Number);
  return m * 60 + s;
}

export default function VideoPlayer() {
  const playerRef = useRef<YouTubePlayer | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedVideo = useVideoStore((s) => s.selectedVideo);
  const cookingSteps = useVideoStore((s) => s.cookingSteps);
  const currentStepIndex = useVideoStore((s) => s.currentStepIndex);
  const playerStatus = useVideoStore((s) => s.playerStatus);
  const isActionDetected = useVideoStore((s) => s.isActionDetected);
  const setPlayerStatus = useVideoStore((s) => s.setPlayerStatus);
  const setCurrentStepIndex = useVideoStore((s) => s.setCurrentStepIndex);
  const setIsActionDetected = useVideoStore((s) => s.setIsActionDetected);

  // 스텝 정보를 interval 내부에서 최신값으로 읽기 위한 ref
  const stepsRef = useRef(cookingSteps);
  const stepIndexRef = useRef(currentStepIndex);
  useEffect(() => { stepsRef.current = cookingSteps; }, [cookingSteps]);
  useEffect(() => { stepIndexRef.current = currentStepIndex; }, [currentStepIndex]);

  // 영상 재생 중 현재 시간 폴링 → end_time 도달 시 일시정지 + 다음 단계로 이동
  useEffect(() => {
    if (playerStatus !== "playing") {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }

    intervalRef.current = setInterval(() => {
      if (!playerRef.current) return;
      const currentTime: number = playerRef.current.getCurrentTime();
      const step = stepsRef.current[stepIndexRef.current];
      if (!step) return;

      if (currentTime >= timeToSeconds(step.end_time)) {
        playerRef.current.pauseVideo();
        const nextIndex = stepIndexRef.current + 1;
        if (nextIndex < stepsRef.current.length) {
          setCurrentStepIndex(nextIndex);
        }
      }
    }, 500);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playerStatus, setCurrentStepIndex]);

  // 제스처/도구 인식 완료 시 영상 재개
  useEffect(() => {
    if (isActionDetected && playerStatus === "paused" && playerRef.current) {
      playerRef.current.playVideo();
      setIsActionDetected(false);
    }
  }, [isActionDetected, playerStatus, setIsActionDetected]);

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

  const waitingStep = cookingSteps[currentStepIndex];
  const isWaiting = playerStatus === "paused" && cookingSteps.length > 0 && !!waitingStep;

  function handleForcePause() {
    if (!playerRef.current) return;
    playerRef.current.pauseVideo();
    const nextIndex = stepIndexRef.current + 1;
    if (nextIndex < stepsRef.current.length) setCurrentStepIndex(nextIndex);
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

      {/* 테스트용 버튼 — CV 모델 연동 후 제거 */}
      {cookingSteps.length > 0 && playerStatus === "playing" && (
        <button
          onClick={handleForcePause}
          className="px-3 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
        >
          [테스트] 지금 일시정지
        </button>
      )}

      {isWaiting && (
        <div className="flex flex-col items-center gap-1">
          {/* 테스트용 버튼 — CV 모델 연동 후 제거 */}
          <button
            onClick={() => setIsActionDetected(true)}
            className="mt-1 px-4 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
          >
            수동으로 다음 단계 시작
          </button>
        </div>
      )}
      <p className="text-xs text-gray-400">상태: {playerStatus}</p>
    </div>
  );
}
