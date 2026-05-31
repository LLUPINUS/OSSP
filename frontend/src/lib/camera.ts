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
      // 미리보기 화질 위해 720p 요청. 정지 구간 단발 추론이라 스트림 부담이 거의 없고,
      // CV로 보낼 프레임은 캡처 시 다운스케일하면 된다(README 6).
      width: { ideal: 1280 },
      height: { ideal: 720 },
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
