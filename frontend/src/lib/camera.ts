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

// 미리보기 화질 위해 720p 요청. 정지 구간 단발 추론이라 스트림 부담이 거의 없고,
// CV로 보낼 프레임은 캡처 시 다운스케일하면 된다(README 6).
const SIZE = { width: { ideal: 1280 }, height: { ideal: 720 } } as const;

export async function startCamera(mode: Facing = facing): Promise<MediaStream> {
  stopCamera(); // 기존 스트림 정리 후 재요청(전/후면 전환 포함)
  facing = mode;

  let s = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: mode }, ...SIZE },
    audio: false,
  });

  // 다중 카메라 폰은 facingMode만 주면 후면 '초광각' 렌즈를 기본으로 잡는 경우가 있어
  // 광각/어안처럼 보인다. 권한 획득 후(=라벨이 채워진 뒤) 메인 렌즈 deviceId로 재선택한다.
  // 적합한 후보가 없거나 실패하면 1차 스트림을 그대로 유지(graceful).
  if (mode === "environment") {
    try {
      const mainId = await pickMainBackCameraId();
      const curId = s.getVideoTracks()[0]?.getSettings().deviceId;
      if (mainId && mainId !== curId) {
        const better = await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: mainId }, ...SIZE },
          audio: false,
        });
        s.getTracks().forEach((t) => t.stop()); // 1차 스트림 정리
        s = better;
      }
    } catch {
      /* 렌즈 재선택 실패 → 1차 스트림 유지 */
    }
  }

  stream = s;
  return stream;
}

// 후면 카메라 중 '메인'(초광각/망원/심도 아님) 렌즈의 deviceId를 고른다.
// 라벨은 권한 부여 후에만 채워진다. 카메라가 1개뿐이거나 못 고르면 null(=facingMode 유지).
async function pickMainBackCameraId(): Promise<string | null> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cams = devices.filter((d) => d.kind === "videoinput" && d.label);
  if (cams.length <= 1) return null;

  const backRe = /back|rear|environment|후면|뒷/i;
  const back = cams.filter((d) => backRe.test(d.label));
  const pool = back.length ? back : cams;

  // 안드로이드 크롬 라벨 "camera2 N, facing back" → 인덱스 N(메인은 보통 0). iOS 등은 0.
  const camIdx = (l: string): number => {
    const m = l.match(/camera2?\s+(\d+)/i);
    return m ? Number(m[1]) : 0;
  };
  // 낮을수록 메인. 초광각/망원/심도는 강한 페널티, 일반 '광각/wide' 표기는 약한 페널티.
  const rank = (l: string): number => {
    if (/ultra|초광각|tele|망원|depth|심도|truedepth|infrared|적외/i.test(l))
      return 3000 + camIdx(l);
    if (/wide|광각/i.test(l)) return 1000 + camIdx(l);
    return camIdx(l);
  };

  const best = [...pool].sort((a, b) => rank(a.label) - rank(b.label))[0];
  return best?.deviceId ?? null;
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
