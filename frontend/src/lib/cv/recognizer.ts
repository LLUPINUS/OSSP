// CV 추론 모듈 — 판단 로직 없음(그건 Phase 2 decide.ts).
// MediaPipe Tasks(GestureRecognizer + ObjectDetector)를 브라우저에서 로드하고,
// 한 프레임을 넣으면 손/도구 감지 결과를 정규화된 shape로 돌려준다.
//
// 옵션은 ai/test_gesture_object.py에서 확정한 값(설계문서 §3.3):
//   gesture: numHands 2, 신뢰도 3종 0.5 / object: scoreThreshold 0.40, maxResults 5
// 결과 shape는 설계문서 §3.4.
import {
  FilesetResolver,
  GestureRecognizer,
  ObjectDetector,
} from "@mediapipe/tasks-vision";

// predev/prebuild가 복사해 둔 정적 경로(public/).
const WASM_PATH = "/mediapipe-wasm";
const GESTURE_MODEL = "/models/gesture_03.task";
const OBJECT_MODEL = "/models/object_08.tflite";

export interface HandResult {
  handedness: string; // "Left" | "Right"
  gesture: string; // top 제스처 라벨 (index_grip/light_grip/pen_grip/tongs/none)
  gestureScore: number;
  landmarks: { x: number; y: number; z: number }[]; // 21개, 정규화 [0,1]
}

export interface ObjectResult {
  label: string; // knife/ladle/spatula/spoon/tongs
  score: number;
  bbox: { originX: number; originY: number; width: number; height: number }; // 픽셀
}

export interface FrameResult {
  hands: HandResult[];
  objects: ObjectResult[];
}

let gesture: GestureRecognizer | null = null;
let object: ObjectDetector | null = null;
let initPromise: Promise<void> | null = null;
let activeDelegate: "GPU" | "CPU" | null = null;

export function getDelegate(): "GPU" | "CPU" | null {
  return activeDelegate;
}

async function build(delegate: "GPU" | "CPU"): Promise<void> {
  const vision = await FilesetResolver.forVisionTasks(WASM_PATH);
  gesture = await GestureRecognizer.createFromOptions(vision, {
    baseOptions: { modelAssetPath: GESTURE_MODEL, delegate },
    runningMode: "VIDEO",
    numHands: 2,
    minHandDetectionConfidence: 0.5,
    minHandPresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });
  object = await ObjectDetector.createFromOptions(vision, {
    baseOptions: { modelAssetPath: OBJECT_MODEL, delegate },
    runningMode: "VIDEO",
    scoreThreshold: 0.4,
    maxResults: 5,
  });
  activeDelegate = delegate;
}

// 두 모델 로드(멱등). GPU 우선, 실패 시 CPU로 폴백.
export function createRecognizers(): Promise<void> {
  if (initPromise) return initPromise;
  initPromise = (async () => {
    try {
      await build("GPU");
    } catch (e) {
      console.warn("[cv] GPU delegate 실패 → CPU 폴백", e);
      await build("CPU");
    }
  })();
  return initPromise;
}

// 한 프레임 추론. createRecognizers() 완료 후 호출해야 함.
// tsMs는 각 모델에 대해 단조 증가해야 함(performance.now() 사용 권장).
export function recognizeFrame(
  video: HTMLVideoElement,
  tsMs: number,
): FrameResult {
  if (!gesture || !object) {
    throw new Error("recognizer 미초기화 — createRecognizers()를 먼저 await 하세요.");
  }

  const g = gesture.recognizeForVideo(video, tsMs);
  const hands: HandResult[] = (g.landmarks ?? []).map((lm, i) => ({
    handedness: g.handedness?.[i]?.[0]?.categoryName ?? "",
    gesture: g.gestures?.[i]?.[0]?.categoryName ?? "none",
    gestureScore: g.gestures?.[i]?.[0]?.score ?? 0,
    landmarks: lm.map((p) => ({ x: p.x, y: p.y, z: p.z })),
  }));

  const o = object.detectForVideo(video, tsMs);
  const objects: ObjectResult[] = (o.detections ?? []).map((d) => {
    const top = d.categories?.[0];
    const b = d.boundingBox;
    return {
      label: top?.categoryName ?? "",
      score: top?.score ?? 0,
      bbox: {
        originX: b?.originX ?? 0,
        originY: b?.originY ?? 0,
        width: b?.width ?? 0,
        height: b?.height ?? 0,
      },
    };
  });

  return { hands, objects };
}

export function closeRecognizers(): void {
  gesture?.close();
  object?.close();
  gesture = null;
  object = null;
  initPromise = null;
  activeDelegate = null;
}
