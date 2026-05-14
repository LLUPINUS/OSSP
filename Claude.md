# Project: 실시간 CV기반 유튜브 요리 영상 제어 서비스
**프로젝트 목표:** 사용자의 요리 행동을 실시간으로 인식(MediaPipe/CV)하여, 진행 상황에 맞춰 유튜브 요리 영상의 재생/일시정지를 자동으로 제어하는 웹 서비스.

## 👤 My Role (강진주)
- **담당 파트:** 프론트엔드(React) 및 백엔드 외부 API 연동 로직
- **주요 임무:** 1. YouTube 검색 및 영상 제어 UI 구현
  2. YouTube 자막 추출 및 Gemini API를 활용한 '요리 단계(Step)' 데이터 정제 로직 구현
  3. 실시간 행동 인식(CV 파트)과 영상 제어(YouTube iframe) 간의 Sync 상태 관리

## 🛠 Tech Stack & Versions (Strictly Enforced)
이 프로젝트는 버전 호환성이 매우 중요하므로, 코드 작성 및 패키지 설치 시 반드시 아래의 버전을 준수할 것.

### Frontend
- **Node.js:** v20.x (LTS)
- **Framework:** React 18.2.x
- **Language:** TypeScript 5.x
- **State Management:** Zustand 4.5.x
- **Styling:** TailwindCSS 3.4.x
- **CV Library:** `@mediapipe/tasks-vision` (최신 버전 사용)
- **Video Control:** YouTube iframe Player API (`react-youtube` 라이브러리 사용 시 React 18 호환성 확인)

### Backend (API Logic)
- **Language:** Python 3.11.9 (반드시 3.11.x 환경 유지)
- **LLM API:** `google-generativeai`
- **LLM Model:** `gemini-2.0-flash-lite-preview-02-05` (속도 및 비용 최적화를 위해 Flash-Lite 필수 사용)
- **YouTube API:** - 검색용: `google-api-python-client` (YouTube Data API v3)
  - 자막용: `youtube-transcript-api` (최신 안정화 버전)
- **Environment:** `python-dotenv` (API Key는 반드시 `.env`에서 로드)

## 🔗 핵심 연동 API 역할 및 규칙
코드를 작성할 때 다음 API들의 역할 분담을 명확히 지킬 것.
1. **YouTube Data API v3:** 키워드(예: 감자볶음)로 요리 영상을 검색하고 `videoID`를 추출.
2. **YouTube Transcript API:** 추출한 `videoID`를 바탕으로 영상의 타임스탬프와 자막 텍스트 원본 수집.
3. **Gemini API (2.0 Flash Lite):** 자막 원본을 분석하여 요리 단계별 계획표 생성.
   - *규칙:* 반드시 `response_mime_type: "application/json"`을 사용하여 순수 JSON 배열만 반환하도록 강제할 것.
   - *출력 포맷 예시:* `[{"action": "감자 썰기", "start_time": "02:00", "end_time": "03:29"}]`
4. **YouTube iframe API:** Gemini가 생성한 JSON 시간표와 사용자의 실시간 행동 탐지 결과를 비교하여 `playVideo()`, `pauseVideo()` 실행.

## 📝 Coding Conventions & Instructions for Claude
- 백엔드(Python) 코드 작성 시, 모듈 경로가 꼬이지 않도록 파일명은 라이브러리명과 겹치지 않게 주의할 것 (예: `youtube_transcript_api.py` 사용 금지).
- 모든 API 호출부에는 반드시 `try-except` 예외 처리 로직을 포함하여 프론트엔드 단에서 앱이 크래시되지 않도록 할 것.
- API Key 등 민감한 정보는 하드코딩하지 말고 `os.environ.get()`을 사용할 것.
- 프론트엔드(React) 상태 관리는 복잡한 `useState` 남용을 피하고, 영상 재생 상태 및 현재 요리 단계와 같은 전역 상태는 `Zustand` 스토어로 분리하여 관리할 것.