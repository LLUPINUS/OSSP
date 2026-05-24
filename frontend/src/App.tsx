import SearchBar from "./components/SearchBar";
import VideoPlayer from "./components/VideoPlayer";
import CookingSteps from "./components/CookingSteps";
import CameraFeed from "./components/CameraFeed";

function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-6 gap-6">
      <h1 className="text-2xl font-bold text-gray-800">
        실시간 CV 요리 영상 제어 서비스
      </h1>

      <SearchBar />

      <div className="flex gap-6 flex-wrap justify-center">
        <VideoPlayer />
        <CookingSteps />
      </div>

      <CameraFeed />
    </div>
  );
}

export default App;
