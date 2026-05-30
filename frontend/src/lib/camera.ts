// 카메라 스트림 싱글톤 관리자.
// 거치 가이드(CameraGuide)와 동기화 재생(SyncPlayback)이 동일 스트림을 공유한다
// (README 5 — 재요청 금지). 스트림은 모듈 레벨에 보관하고 컴포넌트는 video에 attach만.

type Facing = "environment" | "user";

let stream: MediaStream | null = null;
let facing: Facing = "environment";

export function getStream(): MediaStream | null {
  return stream;
}

export function getFacing(): Facing {
  return facing;
}

export async function startCamera(mode: Facing = facing): Promise<MediaStream> {
  stopCamera(); // 기존 스트림 정리 후 재요청(전/후면 전환 포함)
  facing = mode;
  stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: { ideal: mode },
      width: { ideal: 640 }, // 모바일 성능 고려 해상도 제한(README 6)
      height: { ideal: 480 },
    },
    audio: false,
  });
  return stream;
}

export async function flipCamera(): Promise<MediaStream> {
  return startCamera(facing === "environment" ? "user" : "environment");
}

export function stopCamera(): void {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
}

// 'granted' | 'prompt' | 'denied'. Permissions API 미지원 시 'prompt'로 간주(README 5).
export async function queryCameraPermission(): Promise<PermissionState> {
  try {
    const result = await navigator.permissions.query({
      name: "camera",
    } as unknown as PermissionDescriptor);
    return result.state;
  } catch {
    return "prompt";
  }
}
