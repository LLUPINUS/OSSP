// CV 판단 로직 (Phase 2). recognizer의 프레임 결과 → "지금 무슨 action이 확실히 잡혔나".
// 게이트 방식(정밀/관대)과는 무관 — 여기선 동작 인식만 한다. 매칭은 SyncPlayback이 담당.
//
// 파라미터는 CV팀 확정값(설계문서 §7.1):
//   w1=0.8(object_conf), w2=0.2(grip), threshold=0.7, palm=5(INDEX_FINGER_MCP),
//   스무딩=다수결 비율 0.5(시간 윈도우 ~1s, 프레임 개수 방식으로 전환 가능).
//   distanceThreshold는 미정 → 임시 0.25로 시작해 실측 튜닝.
// 모든 튜닝값은 DEFAULT_CONFIG 한곳에 모음.
import type { FrameResult } from "./recognizer";

// 도구 → action label(영문). ladle·spoon 둘 다 stirring (N:1). (설계문서 §7.1)
export const TOOL_TO_ACTION: Record<string, string> = {
  knife: "cutting",
  tongs: "roasting",
  spatula: "stir_frying",
  ladle: "stirring",
  spoon: "stirring",
};

// 영문 action → 한글 (CookingStep.gesture가 한글이라 정밀 매칭 시 변환용).
export const ACTION_KO: Record<string, string> = {
  cutting: "썰기",
  roasting: "굽기",
  stir_frying: "볶기",
  stirring: "젓기",
};

export type SmoothingConfig =
  | { mode: "time"; windowMs: number; ratio: number } // 최근 windowMs 동안 비율 ratio↑
  | { mode: "count"; windowFrames: number; ratio: number }; // 최근 N프레임 중 비율 ratio↑

export interface DecideConfig {
  w1: number; // object_confidence 가중치
  w2: number; // grip_condition 가중치
  threshold: number; // 가중치합 임계값
  distanceThreshold: number; // palm↔도구중심 정규화 유클리드 거리 임계 (임시값)
  palmLandmark: number; // 손 "중심점" landmark index (5 = INDEX_FINGER_MCP)
  smoothing: SmoothingConfig;
}

export const DEFAULT_CONFIG: DecideConfig = {
  w1: 0.8,
  w2: 0.2,
  threshold: 0.5,
  distanceThreshold: 0.4, // ⚠️ 임시 — CV팀 미확정, 실측 튜닝 대상
  palmLandmark: 5,
  smoothing: { mode: "time", windowMs: 1000, ratio: 0.5 },
};

function dist(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}

// 도구 1개에 대한 판단 중간값 (디버그/진단용).
export interface ObjectExplain {
  label: string;
  mappedAction: string | null; // 매핑 없으면 null
  score: number;
  distance: number; // palm↔도구중심 정규화 거리 (손 없으면 Infinity)
  distOk: boolean; // distance ≤ distanceThreshold
  weighted: number; // w1·score + w2·grip
  weightedOk: boolean; // weighted ≥ threshold
  pass: boolean; // 매핑 && distOk && weightedOk
}

export interface FrameExplain {
  grip: 0 | 1;
  palmPresent: boolean;
  objects: ObjectExplain[];
}

// 한 프레임의 판단 중간값을 전부 계산(어느 게이트가 막는지 진단용).
// evaluateFrame이 이걸 재사용하므로 로직은 한 곳뿐이다.
export function explainFrame(
  frame: FrameResult,
  frameW: number,
  frameH: number,
  cfg: DecideConfig = DEFAULT_CONFIG,
): FrameExplain {
  // grip_condition: 손이 있고 top 제스처가 none이 아니면 1, 아니면 0. (§3.6)
  // ※ PDF §4 step0은 "none→false"(하드)지만, 가중치합에 grip을 쓰려면 소프트(none→0)가
  //   맞다(하드면 w2·grip이 무의미). soft 채택 — CV팀 확인 대상.
  const grip: 0 | 1 = frame.hands.some((h) => h.gesture && h.gesture !== "none")
    ? 1
    : 0;

  // palm 점들(정규화 [0,1] — landmark는 이미 정규화).
  const palms = frame.hands
    .map((h) => h.landmarks[cfg.palmLandmark])
    .filter((p): p is { x: number; y: number; z: number } => !!p);

  const valid = frameW > 0 && frameH > 0;
  const objects: ObjectExplain[] = frame.objects.map((o) => {
    const mappedAction = TOOL_TO_ACTION[o.label] ?? null;
    // 도구 bbox 중심을 프레임 크기로 정규화(손 landmark와 좌표계 통일 — §3.5).
    const cx = valid ? (o.bbox.originX + o.bbox.width / 2) / frameW : 0;
    const cy = valid ? (o.bbox.originY + o.bbox.height / 2) / frameH : 0;
    const distance = palms.length
      ? Math.min(...palms.map((p) => dist(p.x, p.y, cx, cy)))
      : Infinity;
    const distOk = distance <= cfg.distanceThreshold;
    const weighted = cfg.w1 * o.score + cfg.w2 * grip;
    const weightedOk = weighted >= cfg.threshold;
    return {
      label: o.label,
      mappedAction,
      score: o.score,
      distance,
      distOk,
      weighted,
      weightedOk,
      pass: !!mappedAction && valid && distOk && weightedOk,
    };
  });

  return { grip, palmPresent: palms.length > 0, objects };
}

// 한 프레임 평가 → 확실히 잡힌 action(영문) 또는 null. (스무딩 전, 프레임 단위)
// 통과한 도구 중 score 최고의 action을 고른다.
export function evaluateFrame(
  frame: FrameResult,
  frameW: number,
  frameH: number,
  cfg: DecideConfig = DEFAULT_CONFIG,
): string | null {
  const ex = explainFrame(frame, frameW, frameH, cfg);
  let best: { action: string; score: number } | null = null;
  for (const o of ex.objects) {
    if (!o.pass || !o.mappedAction) continue;
    if (!best || o.score > best.score) {
      best = { action: o.mappedAction, score: o.score };
    }
  }
  return best?.action ?? null;
}

// 다수결 스무딩. 윈도우(시간 or 프레임 개수) 안에서 같은 action이 비율 ratio 이상이면 확정.
// 윈도우가 한 번도 안 찬 동안(warmup)에는 null — "~1초(or N프레임) 유지"를 보장하기 위함.
export class ActionSmoother {
  private buf: { t: number; action: string | null }[] = [];
  private start = performance.now();
  private cfg: SmoothingConfig;

  constructor(cfg: SmoothingConfig) {
    this.cfg = cfg;
  }

  reset(now: number = performance.now()): void {
    this.buf = [];
    this.start = now;
  }

  push(action: string | null, now: number = performance.now()): void {
    this.buf.push({ t: now, action });
    if (this.cfg.mode === "time") {
      const cutoff = now - this.cfg.windowMs;
      this.buf = this.buf.filter((e) => e.t >= cutoff);
    } else if (this.buf.length > this.cfg.windowFrames) {
      this.buf = this.buf.slice(-this.cfg.windowFrames);
    }
  }

  // 확정된 action 또는 null. null 프레임도 분모에 포함(미검출은 비율을 깎음).
  result(now: number = performance.now()): string | null {
    // warmup: 아직 한 윈도우만큼 관측 못 했으면 보류.
    if (this.cfg.mode === "time") {
      if (now - this.start < this.cfg.windowMs) return null;
    } else if (this.buf.length < this.cfg.windowFrames) {
      return null;
    }
    if (this.buf.length === 0) return null;

    const counts = new Map<string, number>();
    for (const e of this.buf) {
      if (e.action) counts.set(e.action, (counts.get(e.action) ?? 0) + 1);
    }
    let bestAction: string | null = null;
    let bestCount = 0;
    for (const [a, c] of counts) {
      if (c > bestCount) {
        bestAction = a;
        bestCount = c;
      }
    }
    return bestAction && bestCount / this.buf.length >= this.cfg.ratio
      ? bestAction
      : null;
  }
}

// 프레임 평가 + 스무딩을 묶은 편의 객체. SyncPlayback이 게이트당 하나 만들어 쓴다.
export function createDecider(cfg: DecideConfig = DEFAULT_CONFIG) {
  const smoother = new ActionSmoother(cfg.smoothing);
  return {
    // 게이트 진입 시 호출 — 스무딩 윈도우/warmup 초기화.
    reset(now?: number) {
      smoother.reset(now);
    },
    // 한 프레임 처리. confirmed≠null 이면 스무딩까지 만족(게이트 통과 후보).
    process(
      frame: FrameResult,
      frameW: number,
      frameH: number,
      now: number = performance.now(),
    ): { frameAction: string | null; confirmed: string | null } {
      const frameAction = evaluateFrame(frame, frameW, frameH, cfg);
      smoother.push(frameAction, now);
      return { frameAction, confirmed: smoother.result(now) };
    },
  };
}
