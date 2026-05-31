import { useEffect, useRef, useState } from "react";
import { useVideoStore } from "../../store/useVideoStore";
import {
  flipCamera,
  queryCameraPermission,
  startCamera,
  stopCamera,
} from "../../lib/camera";
import { BackIcon, CameraIcon, CameraOffIcon, FlipCameraIcon } from "../icons";

type Gate = "request" | "denied" | "granted";

export default function CameraGuide() {
  const setPhase = useVideoStore((s) => s.setPhase);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [gate, setGate] = useState<Gate>("request");

  function attach(stream: MediaStream) {
    if (videoRef.current) videoRef.current.srcObject = stream;
  }

  // 진입 시 권한 상태 분기 (README 5).
  // granted면 바로 미리보기, prompt면 요청 카드, denied면 거부 카드.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const perm = await queryCameraPermission();
      if (cancelled) return;
      if (perm === "granted") {
        try {
          const s = await startCamera();
          if (cancelled) return;
          attach(s);
          setGate("granted");
        } catch {
          if (!cancelled) setGate("denied");
        }
      } else {
        setGate(perm === "denied" ? "denied" : "request");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // "카메라 허용하기" / "다시 시도" — 반드시 사용자 탭 안에서 getUserMedia 호출(iOS).
  async function handleAllow() {
    try {
      const s = await startCamera();
      attach(s);
      setGate("granted");
    } catch {
      setGate("denied");
    }
  }

  async function handleFlip() {
    try {
      const s = await flipCamera();
      attach(s);
    } catch {
      /* 전환 실패 시 기존 화면 유지 */
    }
  }

  function handleBack() {
    stopCamera();
    setPhase("results");
  }

  // "같이 요리 시작" — 스트림은 동기화 재생에서 재사용하므로 멈추지 않는다.
  function handleStart() {
    setPhase("processing");
  }

  return (
    <div className="relative flex-1 overflow-hidden bg-[#161618] text-white">
      {/* 후면 카메라 미리보기 */}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
      />
      {gate !== "granted" && (
        <div className="absolute inset-0 bg-[radial-gradient(125%_85%_at_50%_32%,#2c2c30_0%,#161618_72%)]">
          <div className="absolute left-1/2 top-[42%] flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2.5 text-white/20">
            <CameraIcon className="h-[34px] w-[34px]" />
            <span className="text-[12px] font-medium tracking-wide">
              후면 카메라 미리보기
            </span>
          </div>
        </div>
      )}

      {/* 뒤로 */}
      <button
        onClick={handleBack}
        aria-label="뒤로"
        className="absolute left-4 top-4 z-[4] flex h-10 w-10 items-center justify-center rounded-full bg-black/30 backdrop-blur-sm transition-colors active:bg-black/50"
      >
        <BackIcon className="h-[22px] w-[22px]" />
      </button>

      {/* 하단 안내 + 컨트롤 */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/[0.84] via-black/50 to-transparent px-[22px] pb-7 pt-[34px]">
        <div className="mb-5 text-center text-[14.5px] font-semibold tracking-[-0.01em]">
          화구와 조리대가 잘 나오는지 확인해주세요
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleFlip}
            aria-label="카메라 전환"
            className="flex h-[54px] w-[54px] shrink-0 items-center justify-center rounded-full border-[1.5px] border-white/45 bg-white/[0.08] transition-transform active:scale-95"
          >
            <FlipCameraIcon className="h-[22px] w-[22px]" />
          </button>
          <button
            onClick={handleStart}
            className="h-[54px] flex-1 rounded-[15px] bg-white text-base font-bold tracking-[-0.01em] text-ink transition-transform active:scale-[0.985]"
          >
            같이 요리 시작
          </button>
        </div>
      </div>

      {/* 권한 게이트 */}
      {gate !== "granted" && (
        <div className="absolute inset-0 z-[8] flex items-center justify-center bg-black/[0.82] p-8 backdrop-blur-md">
          <div className="flex w-full max-w-[300px] flex-col items-center rounded-[22px] bg-white px-[26px] pb-6 pt-[30px] text-center text-ink shadow-[0_24px_60px_-16px_rgba(0,0,0,0.5)]">
            {gate === "request" ? (
              <>
                <div className="mb-[18px] flex h-[60px] w-[60px] items-center justify-center rounded-[18px] bg-accent/10 text-accent-ink">
                  <CameraIcon className="h-[30px] w-[30px]" />
                </div>
                <div className="text-[18px] font-extrabold tracking-[-0.02em]">
                  카메라 접근을 허용해 주세요
                </div>
                <div className="mt-2.5 text-[13px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
                  CookSync가 요리 동작을 인식해 영상을 동기화하려면 카메라
                  권한이 필요해요
                </div>
                <button
                  onClick={handleAllow}
                  className="mt-5 h-[50px] w-full rounded-[14px] bg-ink text-[15px] font-bold tracking-[-0.01em] text-white transition-transform active:scale-[0.98]"
                >
                  카메라 허용하기
                </button>
              </>
            ) : (
              <>
                <div className="mb-[18px] flex h-[60px] w-[60px] items-center justify-center rounded-[18px] bg-fill text-ink-3">
                  <CameraOffIcon className="h-[30px] w-[30px]" />
                </div>
                <div className="text-[18px] font-extrabold tracking-[-0.02em]">
                  카메라 권한이 차단됐어요
                </div>
                <div className="mt-2.5 text-[13px] font-medium leading-relaxed tracking-[-0.01em] text-ink-3">
                  한 번 차단하면 버튼으로는 다시 물어볼 수 없어요. 주소창의 사이트
                  설정에서 카메라를 ‘허용’으로 바꾼 뒤 새로고침해 주세요.
                </div>
                <button
                  onClick={() => window.location.reload()}
                  className="mt-5 h-[50px] w-full rounded-[14px] bg-ink text-[15px] font-bold tracking-[-0.01em] text-white transition-transform active:scale-[0.98]"
                >
                  새로고침하고 다시 시도
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
