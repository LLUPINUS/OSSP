import { useEffect, useRef } from "react";
import { useVideoStore } from "../store/useVideoStore";

export default function CameraFeed() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const setIsActionDetected = useVideoStore((s) => s.setIsActionDetected);

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch {
        console.error("카메라 접근 실패");
      }
    }

    startCamera();

    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="w-64 h-48 rounded border bg-black object-cover"
      />
      <p className="text-xs text-gray-500">
        MediaPipe 행동 인식 — 준비 중
      </p>
    </div>
  );
}
