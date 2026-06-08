import { useEffect, useRef, useState } from "react";
import YouTube, {
  type YouTubeEvent,
  type YouTubePlayer,
  type YouTubeProps,
} from "react-youtube";
import { useVideoStore } from "../../store/useVideoStore";
import { getStream, stopCamera } from "../../lib/camera";
import { enterLandscape, exitLandscape } from "../../lib/orientation";
import { createRecognizers, recognizeFrame } from "../../lib/cv/recognizer";
import { createDecider, ACTION_KO, DEFAULT_CONFIG } from "../../lib/cv/decide";
import { CheckIcon, PlayIcon } from "../icons";

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

// 인식됨 → 다음 단계 전환까지 잠깐 보여주는 시간 (ms)
const RECOGNIZED_HOLD = 1200;

// 게이트 방식 (설계문서 §7.2). 관대로 되돌리려면 "lenient"로만 바꾸면 됨.
//  lenient: 유효한 요리 동작이 잡히면 재개 (라벨은 표시용)
//  precise: 잡힌 action이 현재 단계 expected(gesture, 한글)와 일치할 때만 재개
const GATE_MODE: "lenient" | "precise" = "precise";

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
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cvLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const gateGenRef = useRef(0); // 진행 중 비동기 게이트 무효화용 세대 토큰
  const deciderRef = useRef(createDecider(DEFAULT_CONFIG));

  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [controlsVisible, setControlsVisible] = useState(true);

  // interval/timer에서 최신값 읽기용 ref
  const stepsRef = useRef(cookingSteps);
  const playingRef = useRef(playing);
  // 다음에 "그 단계 start_time에서 멈춰 동작을 기다릴" 단계 index.
  // 설계: 각 단계 시작 전에 정지 → 그 단계 동작 인식 시 그 단계 영상 재생.
  const pendingStepRef = useRef(0);
  useEffect(() => {
    stepsRef.current = cookingSteps;
  }, [cookingSteps]);
  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  // ── 타이머/컨트롤 헬퍼 ──
  function clearGate() {
    gateGenRef.current++; // 진행 중인 비동기 게이트(모델 로드/추론 루프) 무효화
    if (gateTimerRef.current) clearTimeout(gateTimerRef.current);
    gateTimerRef.current = null;
    if (cvLoopRef.current) clearInterval(cvLoopRef.current);
    cvLoopRef.current = null;
  }
  function clearHideTimer() {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = null;
  }
  function scheduleHide() {
    clearHideTimer();
    hideTimerRef.current = setTimeout(() => setControlsVisible(false), 3000);
  }
  // 탭/조작 시: 컨트롤 표시 후 잠시 뒤 자동 숨김 (재생/정지 무관)
  function revealControls() {
    setControlsVisible(true);
    scheduleHide();
  }
  // 영상 탭: 유튜브처럼 컨트롤을 토글한다. 보이면 숨기고, 숨겨져 있으면 표시(잠시 후 자동 숨김).
  function toggleControls() {
    if (controlsVisible) {
      setControlsVisible(false);
      clearHideTimer();
    } else {
      revealControls();
    }
  }
  // 재생 시작 직후: 잠깐 표시 후 자동 숨김
  function showThenHide() {
    setControlsVisible(true);
    scheduleHide();
  }
  // 일시정지/분석 중: 컨트롤 유지 (표시는 !playing이 보장, 자동 숨김만 취소)
  function holdControls() {
    setControlsVisible(true);
    clearHideTimer();
  }

  // 인식됨 → 이어서 재생. seek 없이 현재 위치(멈춘 단계 start)부터 계속 재생하고,
  // 다음 단계 start_time에서 폴링이 다시 게이트한다.
  function resumeAfterGate() {
    clearGate();
    pendingStepRef.current += 1; // 다음 게이트 대상 = 다음 단계
    const p = playerRef.current;
    p?.playVideo();
    setPlaying(true);
    setAiGateState("waiting");
    showThenHide();
  }

  // 단계 start 도달(또는 수동 점프) → 일시정지 후 인식 사이클 (카메라 10fps 추론 + 판단).
  // pendingStepRef.current 단계의 동작을 기다린다(설계: 단계 시작 전에 멈춰 그 단계 동작 대기).
  function triggerGate() {
    const p = playerRef.current;
    if (!p) return;
    const gateStep = pendingStepRef.current;
    if (gateStep >= stepsRef.current.length) return; // 게이트할 단계 없음(마지막 이후)
    p.pauseVideo();
    setPlaying(false); // 폴링 정지
    setCurrentStepIndex(gateStep); // 표시·하이라이트 = 멈춘(=수행할) 단계
    showThenHide(); // 분석 중에도 일반 상태처럼 잠시 뒤 자동 숨김 (상태는 오른쪽 패널이 표시)
    setAiGateState("analyzing");

    clearGate(); // 이전 게이트 정리 + 세대 증가
    const gen = gateGenRef.current;

    void (async () => {
      try {
        await createRecognizers(); // 최초 1회 모델 로드(이후 즉시 반환)
      } catch (e) {
        // 모델 로드 실패 → analyzing 유지, 사용자가 수동(다음/재생)으로 진행
        console.error("[cv] 모델 로드 실패 — 수동 진행으로 폴백", e);
        return;
      }
      if (gen !== gateGenRef.current) return; // 그새 취소(수동 진행 등)

      deciderRef.current.reset();
      cvLoopRef.current = setInterval(() => {
        const v = camVideoRef.current;
        if (!v || v.videoWidth === 0) return;

        let confirmed: string | null;
        try {
          const r = recognizeFrame(v, performance.now());
          confirmed = deciderRef.current.process(
            r,
            v.videoWidth,
            v.videoHeight,
          ).confirmed;
        } catch (e) {
          console.error("[cv] 추론 오류", e);
          return;
        }
        if (!confirmed) return; // 아직 확정 안 됨 → 계속 대기(사용자 페이스)

        // 정밀 모드: 확정 action이 이 단계 동작(gesture, 한글)과 일치해야 통과
        if (GATE_MODE === "precise") {
          const expectedKo = stepsRef.current[gateStep]?.gesture;
          if (expectedKo && ACTION_KO[confirmed] !== expectedKo) return;
        }

        // 게이트 통과 → 잠깐 "인식됨" 표시 후 이어서 재생
        if (cvLoopRef.current) clearInterval(cvLoopRef.current);
        cvLoopRef.current = null;
        setAiGateState("recognized");
        gateTimerRef.current = setTimeout(resumeAfterGate, RECOGNIZED_HOLD);
      }, 100); // 10fps
    })();
  }

  // 수동 단계 점프: 해당 단계 start로 이동 후 거기서 게이트(자동 흐름과 동일, 옵션 A).
  function goStep(i: number) {
    clearGate();
    const steps = stepsRef.current;
    const clamped = Math.max(0, Math.min(steps.length - 1, i));
    pendingStepRef.current = clamped;
    const p = playerRef.current;
    p?.seekTo(timeToSec(steps[clamped].start_time), true);
    triggerGate(); // 그 단계 start에서 멈춰 그 단계 동작 대기
  }

  function togglePlay() {
    const p = playerRef.current;
    if (!p) return;
    if (playing) {
      p.pauseVideo();
      setPlaying(false);
      clearGate();
      setAiGateState("waiting");
      holdControls();
    } else {
      void enterLandscape(); // 첫 재생 탭(제스처) 시 가로 고정 시도
      // 분석(게이트) 중에 재생을 누르면 = 그 게이트를 강제로 건너뛴다.
      // → 다음 단계 start에서 다시 멈추도록 게이트 대상을 한 칸 전진.
      if (aiGateState === "analyzing") pendingStepRef.current += 1;
      clearGate();
      p.playVideo();
      setPlaying(true);
      setAiGateState("waiting");
      showThenHide();
    }
  }

  function handleExit() {
    clearGate();
    clearHideTimer();
    exitLandscape();
    stopCamera();
    goHome();
  }

  const onReady = (e: YouTubeEvent) => {
    playerRef.current = e.target;
    setDuration(e.target.getDuration?.() ?? 0);
    // 영상은 0:00부터 시작(인트로 포함) — 첫 단계로 건너뛰지 않는다(설계 a안).
    // 첫 게이트는 재생 중 폴링이 0번 단계 start_time에서 처리한다.
    setElapsed(0);
    setCurrentStepIndex(0);
    pendingStepRef.current = 0; // 첫 게이트 = 0번 단계 start
    // 첫 재생은 사용자 탭으로(자동재생 제한) → 정지 상태로 시작
    setAiGateState("waiting");
    showThenHide(); // 진입 직후 컨트롤 잠깐 표시 후 자동 숨김
  };

  // ── 공유 카메라 스트림 attach + 가로 고정 + 언마운트 정리 ──
  useEffect(() => {
    const s = getStream();
    if (s && camVideoRef.current) camVideoRef.current.srcObject = s;
    // 모델 미리 로드(21MB) — 첫 게이트에서 기다리지 않도록 진입 시 워밍업. 실패해도 무시
    // (게이트 시점에 재시도하고, 끝내 실패하면 수동 진행으로 폴백).
    void createRecognizers().catch(() => {});
    // 진입 시 가로 고정 시도(직전 제스처의 transient activation이 남아있으면 성공,
    // 아니면 첫 재생 탭에서 재시도된다).
    void enterLandscape();
    // 데스크탑: 마우스를 움직이면 컨트롤 표시, 멈추면 3초 뒤 자동 숨김(유튜브식).
    // 모바일엔 mousemove가 없어 영향 없음(탭 토글로 제어).
    const onMove = () => revealControls();
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (gateTimerRef.current) clearTimeout(gateTimerRef.current);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      if (cvLoopRef.current) clearInterval(cvLoopRef.current);
      exitLandscape();
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

  // ── 시간 폴링: 스크럽은 정지 중에도 항상 실제 재생 위치를 반영.
  //    다음 단계 start_time 도달 시 게이트(일시정지+분석)만 재생 중에 수행. ──
  useEffect(() => {
    const id = setInterval(() => {
      const p = playerRef.current;
      if (!p) return;
      const t = p.getCurrentTime();
      setElapsed(t);
      const dur = p.getDuration?.() ?? 0;
      if (dur) setDuration(dur);

      if (!playingRef.current) return; // 게이트 검사는 재생 중에만
      const steps = stepsRef.current;
      const pending = pendingStepRef.current;
      // 다음 게이트 단계의 start_time에 도달하면 → 일시정지 + 그 단계 동작 분석.
      // (각 단계 시작 전에 멈춰 그 단계 동작을 기다린다 — 설계 의도.)
      if (pending < steps.length && t >= timeToSec(steps[pending].start_time)) {
        triggerGate();
      }
    }, 400);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
  const isLast = currentStepIndex >= cookingSteps.length - 1;
  const progress = duration ? Math.min(100, (elapsed / duration) * 100) : 0;
  // 컨트롤 표시는 controlsVisible 단일 제어(자동 숨김·탭 토글). 정지/분석도 동일하게 동작.
  const showControls = controlsVisible;

  return (
    <div className="fixed inset-0 z-50 grid grid-cols-[1fr_210px] grid-rows-1 bg-black max-[680px]:grid-cols-[1fr_172px]">
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

        {/* 영상 탭 레이어: 탭하면 컨트롤 토글 (iframe 위에서 클릭 캡처) */}
        <div className="absolute inset-0 z-[2]" onClick={toggleControls} />

        {/* 중앙 재생 오버레이 (정지 + 컨트롤 표시 시 노출 — 컨트롤과 함께 숨겨짐) */}
        {!playing && showControls && (
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

      {/* ── RIGHT: steps 전용 (카메라 프리뷰는 화면에 표시하지 않음) ── */}
      <div className="flex min-h-0 flex-col border-l border-white/[0.07] bg-white px-[18px] py-4">
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

          {/* 카메라 프리뷰는 화면에 표시하지 않는다. 단, 스트림(트랙)은 계속 살려둬야
              브라우저가 카메라를 끄지 않으므로 video는 sr-only로 렌더만 유지한다
              (display:none이 아님 → 화면에서만 숨김, 추후 CV 프레임 캡처 소스로 사용). */}
          <video ref={camVideoRef} autoPlay muted playsInline className="sr-only" />
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
