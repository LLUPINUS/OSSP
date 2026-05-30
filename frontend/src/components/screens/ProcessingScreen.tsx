import { useEffect, useState } from "react";
import { useVideoStore } from "../../store/useVideoStore";
import { fetchCookingSteps } from "../../lib/api";
import type { CookingStep } from "../../types";
import { CheckIcon } from "../icons";

const RING_CIRC = 408.4; // 2πr, r=65
const STAGE_LABEL = [
  "영상 자막 불러오기",
  "AI가 요리 단계 나누기",
  "단계별 타임라인 정리하기",
];
const STAGE_SUB = [
  "유튜브에서 영상 자막을 가져오고 있어요",
  "AI가 자막을 읽고 요리 단계를 나누고 있어요",
  "단계별 타임라인을 정리하고 있어요",
];

type StageState = "pending" | "active" | "done";
type Status = "loading" | "error";

export default function ProcessingScreen() {
  const video = useVideoStore((s) => s.selectedVideo);
  const setPhase = useVideoStore((s) => s.setPhase);

  const [status, setStatus] = useState<Status>("loading");
  const [stages, setStages] = useState<StageState[]>([
    "active",
    "pending",
    "pending",
  ]);
  const [pct, setPct] = useState(0);
  const [title, setTitle] = useState("요리 단계를 만들고 있어요");
  const [sub, setSub] = useState(STAGE_SUB[0]);
  const [runKey, setRunKey] = useState(0);

  useEffect(() => {
    if (!video) return; // 가드는 렌더 시점에서 처리(아래 early return)

    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const wait = (ms: number) =>
      new Promise<void>((r) => {
        timers.push(setTimeout(r, ms));
      });

    (async () => {
      // 리셋(재시도 대응)
      setStatus("loading");
      setTitle("요리 단계를 만들고 있어요");
      setStages(["active", "pending", "pending"]);
      setSub(STAGE_SUB[0]);
      setPct(20);

      // 실제 요청은 즉시 시작 (백엔드가 자막 추출 + Gemini 분류 + DB 저장/캐싱)
      const fetchP: Promise<{ steps: CookingStep[] } | { error: unknown }> =
        fetchCookingSteps(video).then(
          (steps) => ({ steps }),
          (error) => ({ error })
        );

      await wait(900);
      if (cancelled) return;

      // 가장 무거운 단계 = AI가 단계 나누기 → 여기서 실제 응답을 대기
      setStages(["done", "active", "pending"]);
      setSub(STAGE_SUB[1]);
      setPct(55);

      const res = await fetchP;
      if (cancelled) return;

      if ("error" in res || res.steps.length === 0) {
        setStatus("error");
        return;
      }

      setStages(["done", "done", "active"]);
      setSub(STAGE_SUB[2]);
      setPct(85);
      await wait(700);
      if (cancelled) return;

      setStages(["done", "done", "done"]);
      setPct(100);
      setTitle("준비 완료!");
      setSub("이제 영상과 함께 요리를 시작해요");
      await wait(800);
      if (cancelled) return;

      const store = useVideoStore.getState();
      store.setCookingSteps(res.steps);
      store.setCurrentStepIndex(0);
      store.setPhase("sync");
    })();

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, [video, runKey]);

  if (status === "error" || !video) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3.5 px-9 pb-6 text-center">
        <div className="text-[21px] font-extrabold tracking-[-0.025em] text-ink">
          분석에 실패했어요
        </div>
        <div className="text-[13.5px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
          자막이 없거나 단계를 추출하지 못했어요.
          <br />
          다른 영상으로 다시 시도해보세요.
        </div>
        <button
          onClick={() => setRunKey((k) => k + 1)}
          className="mt-2 h-[50px] w-full max-w-[300px] rounded-[14px] bg-ink text-[15px] font-bold tracking-[-0.01em] text-white transition-transform active:scale-[0.98]"
        >
          다시 시도
        </button>
        <button
          onClick={() => setPhase("camera")}
          className="mt-1 px-3 py-2 text-[13px] font-semibold tracking-[-0.01em] text-ink-3 underline underline-offset-[3px]"
        >
          취소하고 돌아가기
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-9 pb-6 text-center">
      {/* 진행 링 */}
      <div className="relative mb-[34px] h-[150px] w-[150px]">
        <div className="absolute inset-[18px] animate-pulse rounded-full bg-accent/10" />
        <svg className="relative z-[1] h-full w-full -rotate-90" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="65" fill="none" className="stroke-fill" strokeWidth="8" />
          <circle
            cx="75"
            cy="75"
            r="65"
            fill="none"
            className="stroke-accent transition-[stroke-dashoffset] duration-500 ease-out"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={RING_CIRC}
            strokeDashoffset={RING_CIRC * (1 - pct / 100)}
          />
        </svg>
        <div className="absolute inset-0 z-[2] flex items-center justify-center text-[31px] font-extrabold tabular-nums tracking-[-0.035em] text-ink">
          {Math.round(pct)}%
        </div>
      </div>

      <div className="text-[21px] font-extrabold leading-tight tracking-[-0.025em] text-ink">
        {title}
      </div>
      <div className="mt-[11px] min-h-[42px] text-[13.5px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
        {sub}
      </div>

      {/* 3단계 체크리스트 */}
      <div className="mt-[38px] flex w-full max-w-[302px] flex-col gap-[5px]">
        {stages.map((st, i) => (
          <div
            key={i}
            className={`flex items-center gap-3.5 rounded-[14px] px-[15px] py-[13px] transition-colors ${
              st === "active" ? "bg-accent/[0.09]" : "bg-fill"
            }`}
          >
            <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full">
              {st === "pending" && (
                <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-white shadow-[0_0_0_1.5px_#ededed_inset] text-[12px] font-bold tabular-nums text-ink-3">
                  {i + 1}
                </span>
              )}
              {st === "active" && (
                <span className="h-[18px] w-[18px] animate-spin rounded-full border-[2.5px] border-accent/25 border-t-accent" />
              )}
              {st === "done" && (
                <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-success text-white">
                  <CheckIcon className="h-[15px] w-[15px]" />
                </span>
              )}
            </span>
            <span
              className={`flex-1 text-left text-[14px] tracking-[-0.01em] transition-colors ${
                st === "active"
                  ? "font-bold text-ink"
                  : st === "done"
                    ? "font-semibold text-ink-2"
                    : "font-semibold text-ink-3"
              }`}
            >
              {STAGE_LABEL[i]}
            </span>
          </div>
        ))}
      </div>

      <button
        onClick={() => setPhase("camera")}
        className="mt-[30px] px-3 py-2 text-[13px] font-semibold tracking-[-0.01em] text-ink-3 underline underline-offset-[3px]"
      >
        취소하고 돌아가기
      </button>
    </div>
  );
}
