import { useEffect, useState } from "react";
import { useVideoStore } from "./store/useVideoStore";
import HomeScreen from "./components/screens/HomeScreen";
import ResultsScreen from "./components/screens/ResultsScreen";
import CameraGuide from "./components/screens/CameraGuide";
import ProcessingScreen from "./components/screens/ProcessingScreen";
import SyncPlayback from "./components/screens/SyncPlayback";
import CvDebug from "./components/screens/CvDebug";

function App() {
  const phase = useVideoStore((s) => s.phase);

  // dev 전용: #cvdebug 해시면 phase 머신을 우회하고 CV 디버그 화면만 렌더.
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (hash === "#cvdebug") return <CvDebug />;

  return (
    // 데스크탑에선 모바일 폭으로 중앙 정렬, 모바일에선 풀블리드
    <div className="flex min-h-[100dvh] w-full justify-center bg-[#e9e8e6]">
      <div className="relative flex h-[100dvh] w-full max-w-[480px] flex-col overflow-hidden bg-white">
        {phase === "home" && <HomeScreen />}
        {phase === "results" && <ResultsScreen />}
        {phase === "camera" && <CameraGuide />}
        {phase === "processing" && <ProcessingScreen />}
      </div>

      {/* 동기화 재생은 가로 풀스크린 오버레이(폰 컬럼 밖, fixed) */}
      {phase === "sync" && <SyncPlayback />}
    </div>
  );
}

export default App;
