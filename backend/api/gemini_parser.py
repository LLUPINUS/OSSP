import os
import json
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash-lite"

client = genai.Client(api_key=GEMINI_API_KEY)


def parse_cooking_steps(transcript_text: str) -> list[dict]:
    try:
        prompt = f"""다음은 요리 영상의 타임스탬프가 포함된 자막입니다.
각 요리 행동(단계)을 분석하여 아래 JSON 배열 형식으로만 반환하세요.
다른 텍스트는 절대 포함하지 마세요.

형식:
[{{"action": "행동 설명", "start_time": "MM:SS", "end_time": "MM:SS"}}]

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
        return steps if isinstance(steps, list) else []
    except json.JSONDecodeError as e:
        print(f"[gemini_parser] JSON 파싱 오류: {e}")
        return []
    except Exception as e:
        print(f"[gemini_parser] 오류: {e}")
        return []
