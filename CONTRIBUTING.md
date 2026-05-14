# Contributing Guide

프로젝트의 협업 규칙입니다. 작업 시작 전에 한 번 읽어주세요.

## 브랜치 전략
```bash
main      ← 안정 버전 (시연/배포 시점에만 머지)
│
└── develop  ← 통합 개발 브랜치
    │
    ├── feature/db-recipe-model
    ├── feature/api-search-endpoint
    └── feature/fe-video-player
```

- `main`: 항상 동작하는 안정 버전. 직접 push 금지.
- `develop`: 모든 feature 브랜치의 출발점이자 도착점. 직접 push 금지.
- `feature/<영역>-<작업>`: 개별 작업 브랜치. develop에서 분기, develop으로 머지.

### 브랜치 prefix

| Prefix | 용도 | 예시 |
|--------|------|------|
| `db-` | DB 모델, 마이그레이션, 쿼리 | `feature/db-recipe-model` |
| `api-` | API 엔드포인트, 비즈니스 로직 | `feature/api-search-endpoint` |
| `fe-` | 프론트엔드 컴포넌트, 페이지 | `feature/fe-video-player` |
| `ai-` | CV/ML 모델, 추론 서버 | `feature/ai-action-classifier` |
| `infra-` | 빌드, 설정, 협업 문서 | `feature/infra-initial-setup` |

## 작업 시작하기

### 1. Issue 먼저 만들기

모든 작업은 GitHub Issue에서 시작합니다.

1. 저장소의 **Issues** 탭 → **New issue**
2. 제목에 작업 내용을 한 줄로 명확히
3. 본문에 목표, 작업 항목 체크리스트, 참고 자료 작성
4. 본인을 Assignee로 지정

### 2. Issue에서 브랜치 생성

Issue 페이지 우측 사이드바의 **Development** 섹션 → **Create a branch** 클릭.

- Branch name: `feature/<prefix>-<작업>` 형식으로 수정
- Branch source: `develop` (default여야 함)

### 3. 로컬에서 작업

GitHub의 변경사항(새 브랜치)을 로컬로 받아오고 해당 브랜치로 이동합니다.

```bash
git fetch origin
git switch feature/<prefix>-<작업>
```

이제 본인 영역의 코드를 작성하세요. 작성이 끝나면 변경사항을 커밋하고 push합니다.

```bash
git add .
git commit -m "<type>: 무엇을 했는지"
git push
```

> **참고**: Issue에서 브랜치를 만든 경우에는 `git push`만 쳐도 정상 동작합니다. 만약 로컬에서 `git switch -c`로 직접 브랜치를 만들었다면 첫 push 시 에러가 납니다. 그 경우엔 `git push -u origin HEAD`로 첫 push를 하면 됩니다. 그 다음부터는 `git push`만 쳐도 됩니다.(가급적이면 ISSUE 사용해주세요...)


### 4. Pull Request 생성

push 후 GitHub 저장소 페이지로 이동하면, 방금 push한 브랜치에 대해 노란색 배너로 **Compare & pull request** 버튼이 떠있습니다. 클릭하거나, **Pull requests** 탭에서 **New pull request**로 직접 만들 수도 있습니다.

PR 작성 시:
- **base**: `develop` 으로 설정 (현재 default가 develop이 되게끔 설정했기에 거의 develop으로 고정되어 있을것이지만 그래도 한번 확인해주세요)
- **compare**: 본인의 feature 브랜치
- **Title**: 커밋 메시지와 같은 형식 (예: `feat: Recipe 모델 추가`)
- **Description**: 아래 [PR 본문 템플릿](#본문-템플릿) 사용
- 본문에 `Closes #<issue번호>` 명시 → 머지 시 Issue 자동 close
- **Reviewers**에 팀원 1명 이상 지정

마지막으로 **Create pull request** 버튼 클릭.

### 5. 머지

리뷰가 통과되면 GitHub PR 페이지에서 머지를 진행합니다.

1. PR 페이지 하단의 **Merge pull request** 버튼 옆 드롭다운 ▼ 클릭
2. **Squash and merge** 선택 후 클릭
3. 합쳐진 커밋 메시지 확인 (필요시 수정) → **Confirm squash and merge**
4. 머지 완료 후 **Delete branch** 버튼 클릭하여 원격 브랜치 삭제
5. 연결된 Issue가 자동으로 close되었는지 확인

### 6. 로컬 정리

머지 후 로컬 환경도 정리합니다.

```bash
# develop으로 이동 + 머지된 최신 내용 가져오기
git switch develop
git pull origin develop

# 작업 끝난 로컬 브랜치 삭제
git branch -d feature/<prefix>-<작업>
```

## 커밋 메시지 컨벤션

`<type>: <한 줄 요약>` 형식을 따릅니다 (Conventional Commits).

| Type | 용도 |
|------|------|
| `feat` | 새 기능 추가 |
| `fix` | 버그 수정 |
| `db` | DB 스키마, 모델, 마이그레이션 |
| `refactor` | 기능 변경 없는 코드 개선 |
| `docs` | 문서 변경 |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 설정, 의존성 변경 |

### 예시

- feat: YouTube 검색 API 엔드포인트 구현
- fix: 자막 없는 영상 처리 시 NoneType 에러 해결
- db: ActionLabel 테이블에 confidence 컬럼 추가
- docs: 백엔드 README에 환경변수 설정법 추가
- chore: requirements.txt에 httpx 추가

## Pull Request 규칙

### 제목

커밋 메시지와 동일한 형식. 예: `feat: Recipe 모델 추가`

### 본문 템플릿

```markdown
## 변경 사항
- 무엇을 추가/수정/제거했는지

## 테스트
- 어떻게 동작 확인했는지

## 관련 이슈
Closes #<번호>
```

### 머지 방식

기본 **Squash and merge**. 한 PR의 여러 커밋을 1개로 합쳐서 develop에 추가

### 리뷰 규칙

- 최소 1명 이상의 팀원 리뷰 필수
- 리뷰어는 24시간 내 응답 권장
- 코멘트가 달리면 답변 또는 수정 후 머지

## Issue 작성 팁

좋은 Issue는 PR 단위와 1:1로 매칭됩니다. 즉 **하나의 Issue = 하나의 PR**.

- 너무 큰 Issue는 쪼개기 ("백엔드 전체 구현" → "Recipe 모델", "Step 모델", "Recipe API" 등)
- 너무 작은 Issue는 묶기 (오타 수정 같은 건 다른 Issue에 포함)
- Issue 본문에 작업 항목을 체크리스트(`- [ ]`)로 적으면 진행도 추적 가능

## 충돌 해결

내 브랜치 작업 중 develop에 다른 사람의 작업이 머지되면 PR에 충돌이 발생할 수 있습니다.

### 충돌 예방 — 정기적으로 develop 동기화

작업이 길어질 때 develop의 최신 변경사항을 미리 가져와두면 충돌 발생을 줄일 수 있습니다.

```bash
# 1. 현재 작업 임시 저장 (커밋되지 않은 변경사항이 있을 경우)
git stash

# 2. develop 최신화
git switch develop
git pull origin develop

# 3. 내 브랜치로 돌아가서 develop 변경사항 합치기
git switch feature/<prefix>-<작업>
git merge develop

# 4. 임시 저장한 작업 복원
git stash pop
```

### 충돌 발생 시

`git merge develop` 또는 PR 머지 시점에 충돌이 나면:

1. VS Code Source Control 패널에서 충돌 파일이 표시됩니다
2. 각 충돌 파일을 열면 `<<<<<<<`, `=======`, `>>>>>>>` 마커가 보입니다
3. **Accept Current Change**, **Accept Incoming Change**, **Accept Both** 버튼을 눌러 해결
4. 모든 충돌 해결 후:

```bash
git add .
git commit                # 머지 커밋 메시지가 자동으로 채워짐
git push
```

충돌 해결이 어려우면 혼자 해결하지 말고 팀원에게 문의하세요.

## 코드 리뷰 시 신경 쓸 것

- 변수/함수 이름이 직관적인가?
- 불필요한 console.log / print 문이 남아있지 않은가?
- 비밀번호, API 키가 하드코딩되어 있지 않은가? (`.env` 사용 확인)
- 큰 파일(>10MB)이 추가되어 있지 않은가?

