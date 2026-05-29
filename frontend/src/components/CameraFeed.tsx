import { useEffect, useRef, useCallback, useState } from "react";
import { useVideoStore } from "../store/useVideoStore";

// ─────────────────────────────────────────────────────────────────────────────
// [팀원 연동 지점] 아래 함수를 실제 모델 추론으로 교체하세요.
//
// 매개변수:
//   videoEl  - 카메라 <video> 요소 (프레임 캡처용)
//   stepLabel - 현재 필요한 단계 텍스트 (예: "감자 썰기")
//              → 이 값으로 어떤 제스처/도구를 인식해야 할지 판단하세요
//
// 반환값:
//   true  → 필요한 제스처/도구가 인식됨 (영상 재생 트리거)
//   false → 아직 미인식
//
// 예시 교체:
//   const result = await model.detect(videoEl);
//   return result.label === stepLabel && result.confidence > 0.8;
// ─────────────────────────────────────────────────────────────────────────────
async function detectAction(
  _videoEl: HTMLVideoElement,
  _stepLabel: string
): Promise<boolean> {
  // TODO: 여기에 MediaPipe + 커스텀 데이터셋 추론 코드 작성
  return false;
}

export default function CameraFeed() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);

  const cookingSteps = useVideoStore((s) => s.cookingSteps);
  const currentStepIndex = useVideoStore((s) => s.currentStepIndex);
  const playerStatus = useVideoStore((s) => s.playerStatus);
  const setIsActionDetected = useVideoStore((s) => s.setIsActionDetected);

  // 카메라 시작
  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraError("이 브라우저는 카메라를 지원하지 않습니다.");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (e) {
        setCameraError(`카메라 오류: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    startCamera();
    return () => { stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  // 영상이 일시정지 중일 때만 추론 루프 실행
  const runDetection = useCallback(async () => {
    if (!videoRef.current) return;
    const step = cookingSteps[currentStepIndex];
    if (!step) return;

    const detected = await detectAction(videoRef.current, step.action);
    if (detected) setIsActionDetected(true);
  }, [cookingSteps, currentStepIndex, setIsActionDetected]);

  useEffect(() => {
    if (playerStatus !== "paused" || cookingSteps.length === 0) return;

    const id = setInterval(runDetection, 500);
    return () => clearInterval(id);
  }, [playerStatus, cookingSteps.length, runDetection]);

  const currentStep = cookingSteps[currentStepIndex];

  return (
    <div className="flex flex-col items-center gap-2">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="w-64 h-48 rounded border bg-black object-cover"
      />
      {cameraError
        ? <p className="text-xs text-red-500">{cameraError}</p>
        : <p className="text-xs text-gray-500">
            {playerStatus === "paused" && currentStep
              ? `인식 대기 중: ${currentStep.action}`
              : "카메라 대기 중"}
          </p>
      }
    </div>
  );
}
