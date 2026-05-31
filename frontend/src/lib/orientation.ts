// 동기화 재생 화면 가로 고정 (CLAUDE.md 11 — 세로 모바일 동기화 화면 가로 강제).
//
// screen.orientation.lock("landscape")은 대부분의 모바일 브라우저에서
//   (1) 문서가 풀스크린 상태이고  (2) 사용자 제스처 안에서 호출될 때만 동작한다.
// 따라서 재생 버튼 탭(제스처) 시점에 호출한다. 데스크탑/미지원/거부 환경에선
// 조용히 무시하며, 사용자가 직접 폰을 돌리면 레이아웃은 가로로 정상 동작한다.

// lock/unlock은 비표준(experimental)이라 lib.dom의 ScreenOrientation 타입에 없다.
// 런타임엔 존재하므로 선택적 시그니처로 보강한다.
type OrientationLockType = "landscape" | "portrait" | "any" | "natural";
interface LockableOrientation {
  lock?: (orientation: OrientationLockType) => Promise<void>;
  unlock?: () => void;
}

function getOrientation(): LockableOrientation | undefined {
  return screen.orientation as unknown as LockableOrientation | undefined;
}

export async function enterLandscape(): Promise<void> {
  try {
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) {
      await el.requestFullscreen();
    }
  } catch {
    /* 풀스크린 거부(제스처 없음 등) — 무시하고 회전만 시도 */
  }
  try {
    await getOrientation()?.lock?.("landscape");
  } catch {
    /* 미지원/거부 — 사용자가 직접 회전하면 가로 레이아웃은 정상 동작 */
  }
}

export function exitLandscape(): void {
  try {
    getOrientation()?.unlock?.();
  } catch {
    /* noop */
  }
  try {
    if (document.fullscreenElement) void document.exitFullscreen?.();
  } catch {
    /* noop */
  }
}
