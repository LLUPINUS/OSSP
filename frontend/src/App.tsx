import { useVideoStore } from "./store/useVideoStore";
import HomeScreen from "./components/screens/HomeScreen";
import ResultsScreen from "./components/screens/ResultsScreen";
import CameraGuide from "./components/screens/CameraGuide";
import ProcessingScreen from "./components/screens/ProcessingScreen";
import { stopCamera } from "./lib/camera";

function App() {
  const phase = useVideoStore((s) => s.phase);

  return (
    // 데스크탑에선 모바일 폭으로 중앙 정렬, 모바일에선 풀블리드
    <div className="flex min-h-[100dvh] w-full justify-center bg-[#e9e8e6]">
      <div className="relative flex min-h-[100dvh] w-full max-w-[480px] flex-col overflow-hidden bg-white">
        {phase === "home" && <HomeScreen />}
        {phase === "results" && <ResultsScreen />}
        {phase === "camera" && <CameraGuide />}
        {phase === "processing" && <ProcessingScreen />}

        {/* Phase 3에서 구현 — 흐름이 끊기지 않도록 임시 placeholder */}
        {phase === "sync" && <PhasePlaceholder />}
      </div>
    </div>
  );
}

function PhasePlaceholder() {
  const goHome = useVideoStore((s) => s.goHome);
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-8 text-center">
      <div className="text-[15px] font-semibold text-ink-2">
        동기화 재생 (Phase 3)
      </div>
      <div className="text-[13px] text-ink-3">아직 구현 전 단계예요.</div>
      <button
        onClick={() => {
          stopCamera();
          goHome();
        }}
        className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
      >
        처음으로
      </button>
    </div>
  );
}

export default App;
