# Frontend

프로젝트의 웹 프론트엔드 영역입니다.

## 기술 스택
- React 18 + TypeScript
- Vite
- Tailwind CSS
- Zustand
- react-youtube (YouTube IFrame API)
- @mediapipe/tasks-vision (MediaPipe Tasks)

## 처음 세팅하기

### 사전 준비
- Node.js 20 이상 (LTS 권장) — `node -v`로 확인
- 백엔드 서버가 함께 실행 중이어야 검색·단계 분석이 동작합니다 (`../backend/README.md` 참고)

### 1. frontend 폴더로 이동
```bash
cd frontend
```

### 2. 패키지 설치
```bash
npm install
```

### 3. 개발 서버 실행
```bash
npm run dev
```
실행되면 http://localhost:5173 으로 접속합니다.

> 프론트엔드는 `/api` 요청을 Vite 프록시를 통해 백엔드(`http://localhost:8000`)로 전달합니다(`vite.config.ts`). 따라서 **백엔드도 함께 켜져 있어야** 영상 검색과 단계 분석이 동작합니다.

## 자주 쓰는 명령어

```bash
npm run dev      # 개발 서버 (HMR)
npm run build    # 프로덕션 빌드 (tsc 타입체크 + vite build)
npm run preview  # 빌드 결과 로컬 미리보기
npm run lint     # ESLint 검사
```

## 폴더 구조

```
frontend/src/
├── App.tsx                  # phase 기반 화면 전환 셸
├── components/
│   ├── screens/             # Home·Results·PreCookSheet·CameraGuide·Processing·SyncPlayback
│   └── icons.tsx
├── lib/                     # api.ts(검색/단계 호출)·search.ts·camera.ts(스트림 싱글톤)
├── store/useVideoStore.ts   # Zustand phase 상태머신
└── types/index.ts
```

## 트러블슈팅

### 영상 검색은 되는데 결과가 비어 있음
백엔드 `.env`에 유효한 `YOUTUBE_API_KEY`가 설정돼 있는지 확인하세요 (`../backend/README.md`).

### 화면은 뜨는데 검색/단계 분석에서 에러
백엔드 서버(`uvicorn main:app --reload`, 포트 8000)가 함께 실행 중인지 확인하세요.
