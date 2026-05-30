import { useEffect, useRef, useState } from "react";
import YouTube, {
  type YouTubeEvent,
  type YouTubePlayer,
  type YouTubeProps,
} from "react-youtube";
import { useVideoStore } from "../../store/useVideoStore";
import { getStream, stopCamera } from "../../lib/camera";
import { CameraIcon, CheckIcon, PlayIcon } from "../icons";

const OPTS: YouTubeProps["opts"] = {
  width: "100%",
  height: "100%",
  playerVars: {
    autoplay: 0,
    controls: 0, // 기본 컨트롤 숨김 (우리 UI로 제어)
    modestbranding: 1,
    rel: 0,
    playsinline: 1, // iOS 인라인 재생 필수
  },
};

// "MM:SS" / "H:MM:SS" → 초
function timeToSec(t: string): number {
  return t.split(":").map(Number).reduce((acc, v) => acc * 60 + v, 0);
}
function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}
const pad2 = (n: number) => String(n).padStart(2, "0");

// 시뮬레이션 인식 타이밍 (ms)
const SIM_ANALYZE = 2500;
const SIM_RECOGNIZED = 1200;

export default function SyncPlayback() {
  const selectedVideo = useVideoStore((s) => s.selectedVideo);
  const cookingSteps = useVideoStore((s) => s.cookingSteps);
  const currentStepIndex = useVideoStore((s) => s.currentStepIndex);
  const aiGateState = useVideoStore((s) => s.aiGateState);
  const setCurrentStepIndex = useVideoStore((s) => s.setCurrentStepIndex);
  const setAiGateState = useVideoStore((s) => s.setAiGateState);
  const goHome = useVideoStore((s) => s.goHome);

  const playerRef = useRef<YouTubePlayer | null>(null);
  const camVideoRef = useRef<HTMLVideoElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const gateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [controlsVisible, setControlsVisible] = useState(true);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // interval/timer에서 최신값 읽기용 ref
  const stepsRef = useRef(cookingSteps);
  const idxRef = useRef(currentStepIndex);
  const playingRef = useRef(playing);
  useEffect(() => {
    stepsRef.current = cookingSteps;
  }, [cookingSteps]);
  useEffect(() => {
    idxRef.current = currentStepIndex;
  }, [currentStepIndex]);
  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  // ── 컨트롤 자동 숨김 (재생 중 3초 비활동 시) ──
  function scheduleHide() {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => setControlsVisible(false), 3000);
  }
  function revealControls() {
    setControlsVisible(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    if (playingRef.current) scheduleHide();
  }
  // 재생 시작 시 곧 숨기고, 정지/분석 중엔 계속 표시
  useEffect(() => {
    setControlsVisible(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    if (playing) scheduleHide();
  }, [playing]);

  const isLast = currentStepIndex >= cookingSteps.length - 1;

  function clearGate() {
    if (gateTimerRef.current) clearTimeout(gateTimerRef.current);
    gateTimerRef.current = null;
  }

  // ── 공유 카메라 스트림 attach + 언마운트 시 게이트 타이머 정리 ──
  useEffect(() => {
    const s = getStream();
    if (s && camVideoRef.current) camVideoRef.current.srcObject = s;
    return () => {
      clearGate();
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 단계가 바뀌면 현재 항목을 리스트 맨 위로 스크롤 ──
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    requestAnimationFrame(() => {
      const li = list.querySelector<HTMLElement>("[data-cur='true']");
      if (li) list.scrollTo({ top: li.offsetTop, behavior: "smooth" });
    });
  }, [currentStepIndex]);

  // ── 재생 중 폴링: 스크럽 갱신 + 현재 단계 end_time 도달 시 게이트 ──
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const p = playerRef.current;
      if (!p) return;
      const t = p.getCurrentTime();
      setElapsed(t);
      const dur = p.getDuration?.() ?? 0;
      if (dur) setDuration(dur);

      const steps = stepsRef.current;
      const idx = idxRef.current;
      const step = steps[idx];
      if (!step) return;
      // 마지막 단계가 아니고, 현재 단계 끝에 도달하면 → 일시정지 + 분석
      if (idx < steps.length - 1 && t >= timeToSec(step.end_time)) {
        triggerGate();
      }
    }, 400);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  // 단계 끝 도달 → 일시정지 후 인식 사이클
  function triggerGate() {
    const p = playerRef.current;
    if (!p) return;
    p.pauseVideo();
    setPlaying(false); // 폴링 정지
    setAiGateState("analyzing");

    // ───────────────────────────────────────────────────────────────
    // [CV 연동 지점] 아래 타이머는 시뮬레이션이다.
    // 실제 구현은 여기서 카메라 프레임을 캡처해(canvas.toBlob) 1~2초 간격으로
    // POST /recognize {stepId, frame} 호출 → "동작 맞음" 응답 시 recognized로.
    // (UI 상태 전환 로직은 그대로 재사용 — README 6)
    // ───────────────────────────────────────────────────────────────
    clearGate();
    gateTimerRef.current = setTimeout(() => {
      setAiGateState("recognized");
      gateTimerRef.current = setTimeout(() => {
        advanceToNext();
      }, SIM_RECOGNIZED);
    }, SIM_ANALYZE);
  }

  function advanceToNext() {
    clearGate();
    const steps = stepsRef.current;
    const next = idxRef.current + 1;
    if (next >= steps.length) return;
    setCurrentStepIndex(next);
    const p = playerRef.current;
    p?.seekTo(timeToSec(steps[next].start_time), true);
    p?.playVideo();
    setPlaying(true);
    setAiGateState("waiting");
  }

  function goStep(i: number) {
    clearGate();
    revealControls();
    const steps = stepsRef.current;
    const clamped = Math.max(0, Math.min(steps.length - 1, i));
    setCurrentStepIndex(clamped);
    const p = playerRef.current;
    p?.seekTo(timeToSec(steps[clamped].start_time), true);
    p?.playVideo();
    setPlaying(true);
    setAiGateState("waiting");
  }

  function togglePlay() {
    const p = playerRef.current;
    if (!p) return;
    revealControls();
    if (playing) {
      p.pauseVideo();
      setPlaying(false);
      clearGate();
      setAiGateState("waiting");
    } else {
      p.playVideo();
      setPlaying(true);
      setAiGateState("waiting");
    }
  }

  function handleExit() {
    clearGate();
    stopCamera();
    goHome();
  }

  const onReady = (e: YouTubeEvent) => {
    playerRef.current = e.target;
    setDuration(e.target.getDuration?.() ?? 0);
    const steps = stepsRef.current;
    const step = steps[idxRef.current];
    if (step) e.target.seekTo(timeToSec(step.start_time), true);
    // 첫 재생은 사용자 탭으로(자동재생 제한) → 정지 상태로 시작
    setAiGateState("waiting");
  };

  // 안전 가드 (정상 흐름에선 steps>0 보장)
  if (!selectedVideo || cookingSteps.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-[#0a0a0b] text-white">
        <div className="text-sm text-white/70">표시할 요리 단계가 없어요</div>
        <button
          onClick={handleExit}
          className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-ink"
        >
          처음으로
        </button>
      </div>
    );
  }

  const cur = cookingSteps[currentStepIndex];
  const progress = duration ? Math.min(100, (elapsed / duration) * 100) : 0;
  // 정지/분석 중엔 항상 표시, 재생 중엔 자동 숨김 대상
  const showControls = controlsVisible || !playing;

  return (
    <div className="fixed inset-0 z-50 grid grid-cols-[1fr_300px] grid-rows-1 bg-black max-[680px]:grid-cols-[1fr_240px]">
      {/* ── LEFT: YouTube ── */}
      <div className="relative overflow-hidden bg-[radial-gradient(130%_100%_at_50%_38%,#26262a,#101012_75%)]">
        <YouTube
          videoId={selectedVideo.videoId}
          opts={OPTS}
          onReady={onReady}
          onEnd={() => {
            setPlaying(false);
            setAiGateState("waiting");
          }}
          className="absolute inset-0 h-full w-full"
          iframeClassName="absolute inset-0 h-full w-full"
        />

        {/* 영상 탭 레이어: 탭하면 컨트롤을 다시 띄움 (iframe 위에서 클릭 캡처) */}
        <div className="absolute inset-0 z-[2]" onClick={revealControls} />

        {/* 중앙 재생/일시정지 오버레이 (정지 시 노출) */}
        {!playing && (
          <button
            onClick={togglePlay}
            aria-label="재생"
            className="absolute left-1/2 top-1/2 z-[3] flex h-[60px] w-[60px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white backdrop-blur-sm"
          >
            <PlayIcon className="h-6 w-6 translate-x-0.5" />
          </button>
        )}

        {/* 상단: 종료 + 제목 */}
        <div
          className={`absolute inset-x-0 top-0 z-[4] flex items-center gap-2.5 bg-gradient-to-b from-black/60 to-transparent px-[18px] pb-7 pt-3.5 transition-opacity duration-200 ${
            showControls ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
        >
          <button
            onClick={handleExit}
            aria-label="종료"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.16] text-[17px] leading-none text-white"
          >
            ×
          </button>
          <div className="min-w-0 flex-1 truncate text-[13.5px] font-semibold tracking-[-0.01em] text-white">
            {selectedVideo.title}
          </div>
        </div>

        {/* 하단: 스크럽 + 트랜스포트 */}
        <div
          className={`absolute inset-x-0 bottom-0 z-[4] bg-gradient-to-t from-black/[0.72] to-transparent px-[18px] pb-4 pt-[30px] transition-opacity duration-200 ${
            showControls ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
        >
          <div className="flex items-center gap-3 text-[11px] font-semibold tabular-nums text-white/[0.78]">
            <span>{fmt(elapsed)}</span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.24]">
              <i
                className="block h-full rounded-full bg-accent transition-[width] duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span>{duration ? fmt(duration) : "0:00"}</span>
          </div>
          <div className="mt-3 flex items-center justify-center gap-4">
            <button
              onClick={() => goStep(currentStepIndex - 1)}
              aria-label="이전 단계"
              className="flex h-[38px] w-[38px] items-center justify-center rounded-full bg-white/[0.12] text-[15px] text-white active:scale-90"
            >
              ‹
            </button>
            <button
              onClick={togglePlay}
              aria-label="재생/일시정지"
              className="flex h-[46px] w-[46px] items-center justify-center rounded-full bg-white text-[15px] text-ink active:scale-90"
            >
              {playing ? "❚❚" : "▶"}
            </button>
            <button
              onClick={() => goStep(currentStepIndex + 1)}
              aria-label="다음 단계"
              className="flex h-[38px] w-[38px] items-center justify-center rounded-full bg-white/[0.12] text-[15px] text-white active:scale-90"
            >
              ›
            </button>
          </div>
        </div>
      </div>

      {/* ── RIGHT: steps(top) / camera(bottom) ── */}
      <div className="grid min-h-0 grid-rows-[1fr_150px] border-l border-white/[0.07] bg-[#0e0e10]">
        {/* steps 패널 (흰색) */}
        <div className="flex min-h-0 flex-col bg-white px-[18px] py-4">
          <div className="flex shrink-0 items-center justify-between">
            <span className="text-[11px] font-bold tracking-[0.06em] text-ink-3">
              요리 단계
            </span>
            <span className="text-[12px] font-bold tabular-nums text-ink">
              {pad2(currentStepIndex + 1)}{" "}
              <span className="text-ink-3">/ {pad2(cookingSteps.length)}</span>
            </span>
          </div>

          {/* AI 인식 라벨 */}
          <AiLabel
            state={aiGateState}
            playing={playing}
            isLast={isLast}
            stepName={cur.action}
          />

          {/* 현재 단계 */}
          <div className="mt-3.5 shrink-0">
            <div className="text-[11px] font-bold tracking-[0.06em] text-accent-ink">
              STEP {pad2(currentStepIndex + 1)}
            </div>
            <div className="mt-1 text-[22px] font-extrabold leading-tight tracking-[-0.025em] text-ink">
              {cur.action}
            </div>
          </div>

          {/* 전체 리스트 */}
          <div
            ref={listRef}
            className="mt-3.5 flex min-h-0 flex-1 flex-col gap-px overflow-y-auto scroll-smooth"
          >
            {cookingSteps.map((s, i) => {
              const done = i < currentStepIndex;
              const isCur = i === currentStepIndex;
              return (
                <div
                  key={i}
                  data-cur={isCur}
                  onClick={() => goStep(i)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1 py-2 active:bg-fill"
                >
                  <span
                    className={`flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full border-[1.5px] text-[9px] font-bold tabular-nums ${
                      done
                        ? "border-transparent bg-ink-3 text-white"
                        : isCur
                          ? "border-transparent bg-accent text-white"
                          : "border-line text-ink-3"
                    }`}
                  >
                    {done ? <CheckIcon className="h-2.5 w-2.5" /> : pad2(i + 1)}
                  </span>
                  <span
                    className={`min-w-0 flex-1 truncate text-[13px] tracking-[-0.01em] ${
                      done
                        ? "font-medium text-ink-3 line-through"
                        : isCur
                          ? "font-bold text-ink"
                          : "font-medium text-ink-2"
                    }`}
                  >
                    {s.action}
                  </span>
                  <span
                    className={`shrink-0 text-[11px] font-semibold tabular-nums ${
                      isCur ? "text-accent-ink" : "text-ink-3"
                    } ${done ? "opacity-60" : ""}`}
                  >
                    {s.start_time}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 카메라 영역 (다크) */}
        <div className="relative overflow-hidden border-t border-white/[0.07] bg-[radial-gradient(120%_110%_at_50%_35%,#2a2a2e,#121214_80%)]">
          <video
            ref={camVideoRef}
            autoPlay
            muted
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
          />
          <span className="absolute left-[11px] top-[9px] z-[2] flex items-center gap-[5px] rounded-[11px] bg-black/45 px-2 py-1 text-[10px] font-bold text-white">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#ff3b30]" />
            REC
          </span>
          {!getStream() && (
            <div className="absolute left-1/2 top-1/2 z-[1] flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5 text-white/[0.22]">
              <CameraIcon className="h-[22px] w-[22px]" />
              <span className="whitespace-nowrap text-[10.5px] font-semibold">
                카메라 영역
              </span>
            </div>
          )}
          <span className="absolute bottom-[9px] right-[11px] z-[2] flex items-center gap-[5px] rounded-[11px] bg-black/45 px-2 py-1 text-[10px] font-bold text-[#7ee0a0]">
            ● 동기화됨
          </span>
        </div>
      </div>
    </div>
  );
}

function AiLabel({
  state,
  playing,
  isLast,
  stepName,
}: {
  state: "waiting" | "analyzing" | "recognized";
  playing: boolean;
  isLast: boolean;
  stepName: string;
}) {
  let cls = "bg-fill text-ink-3";
  if (state === "analyzing") cls = "bg-accent/10 text-accent-ink";
  if (state === "recognized") cls = "bg-success/[0.12] text-success";

  return (
    <div
      className={`mt-3.5 flex shrink-0 items-center gap-[7px] overflow-hidden rounded-[11px] px-[11px] py-[7px] text-[11.5px] font-semibold tracking-[-0.01em] transition-colors ${cls}`}
    >
      {state === "recognized" ? (
        <CheckIcon className="h-[13px] w-[13px] shrink-0 text-success" />
      ) : (
        <span
          className={`h-[7px] w-[7px] shrink-0 rounded-full ${
            state === "analyzing" ? "animate-pulse bg-accent" : "bg-ink-3"
          }`}
        />
      )}
      <span className="truncate">
        {state === "analyzing" ? (
          <>
            <b className="font-extrabold">{stepName}</b> 동작 분석 중…
          </>
        ) : state === "recognized" ? (
          <>
            <b className="font-extrabold">{stepName}</b> 완료 인식됨
          </>
        ) : !playing ? (
          "일시정지됨"
        ) : isLast ? (
          "재생 중 · 마지막 단계"
        ) : (
          "재생 중 · 감지 대기"
        )}
      </span>
    </div>
  );
}
