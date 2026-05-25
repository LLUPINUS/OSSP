# OSSP

> 실시간 컴퓨터 비전 기반 유튜브 요리 영상 제어 서비스

`2026-1 OSSP (CSC4004-02) 6조 프로젝트`

## 핵심 기능

- **YouTube URL 입력 → 자동 단계 분리**: 자막과 LLM을 활용해 요리 영상을 단계별로 자동 분할
- **실시간 동작 인식**: 스마트폰 카메라로 사용자의 요리 동작을 실시간 분석
- **자동 재생 제어**: 사용자의 진행도에 맞춰 YouTube IFrame API로 영상 재생/일시정지/이동
- **핸즈프리 인터페이스**: 오염된 손으로 화면을 만질 필요 없이 요리에 집중

## 기술 스택

| 영역 | 사용 기술 |
|------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI 0.136, PostgreSQL 18, SQLAlchemy 2.0, Alembic |
| AI / CV | PyTorch, MediaPipe Tasks API, OpenCV |
| External APIs | YouTube Data API v3, YouTube IFrame API, Gemini API |

## 시스템 아키텍처
추후 추가예정

## 프로젝트 구조
```bash
OSSP/
├── backend/    # FastAPI 서버 + PostgreSQL DB
├── frontend/   # React + TypeScript 웹 앱
├── ai/         # PyTorch + MediaPipe AI 추론 서버
└── docs/       # 설계 문서 및 회의록
```

각 영역의 자세한 세팅 가이드는 해당 폴더의 README를 참고하세요.

- [Backend 가이드](./backend/README.md)
- [Frontend 가이드](./frontend/README.md)
- [AI 서버 가이드](./ai/README.md)

## 팀

| 역할 | 담당 영역 |
|------|-----------|
| 팀원 A (Leader) | Frontend, CV/ML |
| 팀원 B | Frontend, Backend (API) |
| 팀원 C | Frontend, Backend (DB) |

## 협업 방식

- **이슈 기반 워크플로우**: 모든 작업은 Issue로 시작해 PR로 종결
- **브랜치 전략**: `main` ← `develop` ← `feature/<영역>-<작업>`
- **자세한 규칙**: [CONTRIBUTING.md](./CONTRIBUTING.md) 참고

## 라이선스

MIT License — [LICENSE](./LICENSE) 참고