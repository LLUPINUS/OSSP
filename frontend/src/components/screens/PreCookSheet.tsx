import { useVideoStore } from "../../store/useVideoStore";
import { VideoGlyphIcon } from "../icons";

export default function PreCookSheet() {
  const open = useVideoStore((s) => s.preCookOpen);
  const video = useVideoStore((s) => s.selectedVideo);
  const setPreCookOpen = useVideoStore((s) => s.setPreCookOpen);
  const setPhase = useVideoStore((s) => s.setPhase);

  function close() {
    setPreCookOpen(false);
  }

  function goCamera() {
    setPreCookOpen(false);
    setPhase("camera");
  }

  return (
    // 항상 DOM에 두고 open 클래스로 토글 → 진입/이탈 모두 트랜지션
    <div className={`absolute inset-0 z-20 ${open ? "" : "pointer-events-none"}`}>
      {/* scrim */}
      <div
        onClick={close}
        className={`absolute inset-0 bg-[rgba(22,19,16,0.5)] transition-opacity duration-[340ms] ${
          open ? "opacity-100" : "opacity-0"
        }`}
      />
      {/* sheet */}
      <div
        className={`absolute inset-x-0 bottom-0 rounded-t-3xl bg-white px-6 pb-[26px] pt-2.5 shadow-[0_-10px_40px_-8px_rgba(0,0,0,0.18)] transition-transform duration-[380ms] ease-[cubic-bezier(0.32,0.72,0,1)] ${
          open ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="mx-auto mb-4 h-[5px] w-[38px] rounded-[3px] bg-[#e2e0dc]" />

        <div className="relative aspect-video w-full overflow-hidden rounded-[15px] bg-gradient-to-br from-[#f1efec] to-[#e7e4df]">
          {video?.thumbnail ? (
            <img
              src={video.thumbnail}
              alt={video.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[#c9c4bc]">
              <VideoGlyphIcon className="h-[34px] w-[34px]" />
            </div>
          )}
          {video?.duration && (
            <span className="absolute bottom-2 right-2 rounded-md bg-black/[0.78] px-2 py-[3px] text-[12px] font-semibold tabular-nums text-white">
              {video.duration}
            </span>
          )}
        </div>

        <div className="mt-4 text-[19px] font-bold leading-snug tracking-[-0.02em] text-ink">
          {video?.title ?? ""}
        </div>
        <div className="mt-2 text-[13px] font-medium tracking-[-0.01em] text-ink-3">
          {video?.channelTitle}
          {video?.duration ? ` · ${video.duration}` : ""}
        </div>

        <button
          onClick={goCamera}
          className="mt-5 flex h-[54px] w-full items-center justify-center gap-2 rounded-[15px] bg-ink text-base font-semibold tracking-[-0.01em] text-white transition-transform active:scale-[0.985]"
        >
          카메라 설정하기
        </button>
      </div>
    </div>
  );
}
