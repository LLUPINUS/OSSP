import os
import json
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash-lite"

client = genai.Client(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# [데이터셋 연동 지점] 팀원의 데이터셋이 확정되면 아래 목록을 업데이트하세요.
# TOOLS  : CV 모델이 인식할 수 있는 주방 도구 목록
# GESTURES: CV 모델이 인식할 수 있는 제스처(행동) 목록
# ─────────────────────────────────────────────────────────────────────────────
TOOLS: list[str] = [
    # 예시: "칼", "도마", "프라이팬", "냄비", "주걱"
    # TODO: 팀원 데이터셋 확정 후 실제 목록으로 교체
]

GESTURES: list[str] = [
    "썰기",
    "젓기",
    "볶기",
    "굽기",
]


class GeminiParseError(Exception):
    """Gemini 호출/파싱 실패. '정상적으로 0건 추출'과 구분하기 위한 예외 (이슈 #5)."""


def parse_cooking_steps(transcript_text: str) -> list[dict]:
    tools_str = ", ".join(TOOLS) if TOOLS else "미확정 (제스처 기준으로만 필터링)"
    gestures_str = ", ".join(GESTURES)

    try:
        prompt = f"""다음은 요리 영상의 타임스탬프가 포함된 자막입니다.

아래 조건에 해당하는 단계만 추출하세요.
조건에 해당하지 않는 단계(재료 준비, 플레이팅, 설명 등)는 제외하세요.

[인식 가능한 제스처]
{gestures_str}

[인식 가능한 주방 도구]
{tools_str}

추출 기준:
- 위 제스처 중 하나가 명확히 포함된 행동만 추출
- 주방 도구가 확정된 경우, 해당 도구를 사용하는 행동만 추출
- 행동 설명은 "감자 썰기", "양파 볶기" 처럼 [재료 + 제스처] 형식으로 작성
- 다른 텍스트는 절대 포함하지 말고 JSON 배열만 반환

형식:
[{{"action": "재료 + 제스처", "start_time": "MM:SS", "end_time": "MM:SS", "gesture": "제스처명"}}]

자막:
{transcript_text}"""

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        steps = json.loads(response.text)
    except json.JSONDecodeError as e:
        # 예외를 []로 삼키면 '정상 0건'과 구분이 안 돼 캐시가 오염된다(이슈 #5). 위로 전파한다.
        raise GeminiParseError(f"Gemini 응답 JSON 파싱 실패: {e}") from e
    except Exception as e:
        raise GeminiParseError(f"Gemini 호출 실패: {e}") from e

    if not isinstance(steps, list):
        raise GeminiParseError(f"Gemini가 리스트가 아닌 응답을 반환했습니다: {type(steps).__name__}")
    return steps
