// dev 전용 CV 디버그 화면 (#cvdebug 해시로 진입, phase 머신 우회).
// 목적: 커스텀 모델이 브라우저에서 실제로 로드·추론되는지 + 폰 fps 검증 (Phase 1).
// 카메라 위에 손 랜드마크/도구 bbox를 그리고, fps·delegate·감지 결과를 표시한다.
// 판단 로직(거리/가중치/스무딩)은 없음 — 그건 Phase 2.
import { useEffect, useRef, useState } from "react";
import { GestureRecognizer } from "@mediapipe/tasks-vision";
import { startCamera, stopCamera, flipCamera } from "../../lib/camera";
import {
  createRecognizers,
  recognizeFrame,
  closeRecognizers,
  getDelegate,
  type FrameResult,
} from "../../lib/cv/recognizer";
import {
  explainFrame,
  DEFAULT_CONFIG,
  type FrameExplain,
} from "../../lib/cv/decide";

type Status = "init" | "ready" | "error";

const EMPTY: FrameResult = { hands: [], objects: [] };

export default function CvDebug() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const loopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fpsRef = useRef({ frames: 0, last: 0, value: 0 });

  const [status, setStatus] = useState<Status>("init");
  const [err, setErr] = useState("");
  const [fps, setFps] = useState(0);
  const [result, setResult] = useState<FrameResult>(EMPTY);
  const [explain, setExplain] = useState<FrameExplain | null>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 }); // MediaPipe가 받는 프레임 해상도(진단용)

  useEffect(() => {
    let cancelled = false;

    function tick() {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) return;

      // 캔버스 내부 해상도 = 영상 본래 해상도 → 도구 bbox(픽셀) 1:1, 랜드마크는 *w/*h
      if (canvas.width !== video.videoWidth) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        // MediaPipe가 실제로 받는 프레임 방향 확인용(가로 1280×720 vs 세로 720×1280)
        setDims({ w: video.videoWidth, h: video.videoHeight });
      }

      let r: FrameResult;
      try {
        r = recognizeFrame(video, performance.now());
      } catch (e) {
        if (loopRef.current) clearInterval(loopRef.current);
        setErr(msg(e));
        setStatus("error");
        return;
      }

      const ex = explainFrame(r, canvas.width, canvas.height);
      draw(canvas, r, ex);

      const f = fpsRef.current;
      f.frames++;
      const now = performance.now();
      if (now - f.last >= 1000) {
        setFps(Math.round((f.frames * 1000) / (now - f.last)));
        f.frames = 0;
        f.last = now;
      }
      setResult(r);
      setExplain(ex);
    }

    (async () => {
      try {
        const stream = await startCamera("environment");
        if (cancelled) return;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play().catch(() => {});
        }
        await createRecognizers(); // 모델 로드 (21MB — 수 초 걸릴 수 있음)
        if (cancelled) return;
        setStatus("ready");
        fpsRef.current = { frames: 0, last: performance.now(), value: 0 };
        loopRef.current = setInterval(tick, 100); // 10fps
      } catch (e) {
        if (cancelled) return;
        setErr(msg(e));
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
      if (loopRef.current) clearInterval(loopRef.current);
      closeRecognizers();
      stopCamera();
    };
  }, []);

  async function flip() {
    try {
      const s = await flipCamera();
      const video = videoRef.current;
      if (video) {
        video.srcObject = s;
        await video.play().catch(() => {});
      }
    } catch (e) {
      setErr(msg(e));
    }
  }

  function close() {
    window.location.hash = "";
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      {/* 상단 바 (가로에선 영상 위에 떠서 영상 높이를 더 확보) */}
      <div className="flex shrink-0 items-center gap-3 px-4 py-2 text-[13px] landscape:absolute landscape:inset-x-0 landscape:top-0 landscape:z-10 landscape:bg-gradient-to-b landscape:from-black/70 landscape:to-transparent">
        <button onClick={close} className="rounded-md bg-white/15 px-2.5 py-1 font-semibold">
          ← 닫기
        </button>
        <span className="font-bold">CV 디버그</span>
        <span className="ml-auto tabular-nums text-white/70">
          {status === "ready" ? (
            <>
              {fps} fps · {dims.w}×{dims.h}{" "}
              <b className={dims.w >= dims.h ? "text-amber-400" : "text-emerald-400"}>
                {dims.w >= dims.h ? "가로" : "세로"}
              </b>{" "}
              · delegate <b className="text-white">{getDelegate()}</b>
            </>
          ) : status === "init" ? (
            "모델 로딩 중…"
          ) : (
            "에러"
          )}
        </span>
        <button onClick={flip} className="rounded-md bg-white/15 px-2.5 py-1 font-semibold">
          카메라 전환
        </button>
      </div>

      {/* 본문: 세로=영상 위·텍스트 아래 / 가로=영상 좌·텍스트 우 */}
      <div className="flex min-h-0 flex-1 flex-col landscape:flex-row">
        {/* 영상 + 오버레이 */}
        <div className="relative flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden">
        <div className="relative max-h-full max-w-full">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="block w-auto max-h-[70vh] landscape:max-h-full landscape:max-w-full"
          />
          <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
        </div>

        {status === "init" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-sm text-white/80">
            모델 로딩 중… (gesture 8MB + object 13MB)
          </div>
        )}
        {status === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80 px-6 text-center">
            <div className="text-sm font-semibold text-red-400">로드/추론 실패</div>
            <div className="max-w-md break-words text-xs text-white/70">{err}</div>
          </div>
        )}
      </div>

      {/* 감지 결과: 세로=하단 / 가로=우측 패널 */}
      <div className="max-h-[24vh] shrink-0 overflow-y-auto border-t border-white/10 px-4 py-2 text-[12px] leading-relaxed landscape:max-h-full landscape:w-56 landscape:border-l landscape:border-t-0 landscape:pt-12">
        <div className="mb-1 font-bold text-white/80">
          손 {result.hands.length} · 도구 {result.objects.length} · grip{" "}
          {explain?.grip ?? 0}
          <span className="ml-2 font-normal text-white/40">
            (통과조건: d≤{DEFAULT_CONFIG.distanceThreshold} · w≥
            {DEFAULT_CONFIG.threshold})
          </span>
        </div>
        {result.hands.map((h, i) => (
          <div key={`h${i}`} className="text-cyan-300">
            ✋ {h.handedness} · {h.gesture} ({(h.gestureScore * 100).toFixed(0)}%)
          </div>
        ))}
        {(explain?.objects ?? []).map((o, i) => (
          <div key={`o${i}`} className={o.pass ? "text-green-400" : "text-white/70"}>
            {o.pass ? "✅" : "❌"} {o.label}
            {o.mappedAction ? `→${o.mappedAction}` : "(미매핑)"} · conf{" "}
            {(o.score * 100).toFixed(0)}% · d=
            {o.distance === Infinity ? "∞" : o.distance.toFixed(2)}
            {o.distOk ? "" : "✗"} · w={o.weighted.toFixed(2)}
            {o.weightedOk ? "" : "✗"}
          </div>
        ))}
      </div>
      </div>
    </div>
  );
}

function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

// ── 캔버스 드로잉 (영상 본래 해상도 좌표계) ──
function draw(canvas: HTMLCanvasElement, r: FrameResult, ex: FrameExplain) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const palmIdx = DEFAULT_CONFIG.palmLandmark;

  // 손: 연결선 + 21점 (+ palm 점 노랑 강조 = 거리 기준점)
  for (const hand of r.hands) {
    const pts = hand.landmarks;
    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = Math.max(2, w / 320);
    for (const c of GestureRecognizer.HAND_CONNECTIONS) {
      const a = pts[c.start];
      const b = pts[c.end];
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x * w, a.y * h);
      ctx.lineTo(b.x * w, b.y * h);
      ctx.stroke();
    }
    ctx.fillStyle = "#f43f5e";
    const rad = Math.max(3, w / 240);
    for (const p of pts) {
      ctx.beginPath();
      ctx.arc(p.x * w, p.y * h, rad, 0, Math.PI * 2);
      ctx.fill();
    }
    const palm = pts[palmIdx];
    if (palm) {
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.arc(palm.x * w, palm.y * h, rad * 2, 0, Math.PI * 2);
      ctx.fill();
    }
    const wrist = pts[0];
    if (wrist) {
      label(ctx, `${hand.handedness} ${hand.gesture}`, wrist.x * w, wrist.y * h, w);
    }
  }

  // palm 점들(픽셀)
  const palms = r.hands
    .map((hd) => hd.landmarks[palmIdx])
    .filter((p): p is { x: number; y: number; z: number } => !!p)
    .map((p) => ({ x: p.x * w, y: p.y * h }));

  // 도구: bbox + 라벨, 매핑된 도구는 palm까지 거리선(통과=초록/탈락=빨강)
  r.objects.forEach((o, i) => {
    const { originX, originY, width, height } = o.bbox;
    const info = ex.objects[i];
    ctx.strokeStyle = "#a3e635";
    ctx.lineWidth = Math.max(2, w / 240);
    ctx.strokeRect(originX, originY, width, height);
    label(ctx, `${o.label} ${(o.score * 100).toFixed(0)}%`, originX, originY, w);

    if (info?.mappedAction && palms.length) {
      const ccx = originX + width / 2;
      const ccy = originY + height / 2;
      let near = palms[0];
      let nd = Infinity;
      for (const p of palms) {
        const d = Math.hypot(p.x - ccx, p.y - ccy);
        if (d < nd) {
          nd = d;
          near = p;
        }
      }
      ctx.strokeStyle = info.distOk ? "#22c55e" : "#ef4444";
      ctx.lineWidth = Math.max(2, w / 300);
      ctx.beginPath();
      ctx.moveTo(near.x, near.y);
      ctx.lineTo(ccx, ccy);
      ctx.stroke();
      label(ctx, `d=${info.distance.toFixed(2)}`, (near.x + ccx) / 2, (near.y + ccy) / 2, w);
    }
  });
}

function label(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  w: number,
) {
  const fs = Math.max(14, w / 40);
  ctx.font = `bold ${fs}px sans-serif`;
  const pad = fs * 0.3;
  const tw = ctx.measureText(text).width;
  const top = Math.max(y, fs + 2);
  ctx.fillStyle = "rgba(0,0,0,0.6)";
  ctx.fillRect(x, top - fs - pad, tw + pad * 2, fs + pad * 1.5);
  ctx.fillStyle = "#fff";
  ctx.fillText(text, x + pad, top - pad);
}
