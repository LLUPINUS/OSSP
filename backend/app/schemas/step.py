from pydantic import BaseModel, Field


class CookingStepOut(BaseModel):
    """LLM이 추출한(또는 캐시에서 복원한) 요리 단계 1건."""

    action: str = Field(..., description="단계 설명 (재료 + 제스처, 예: '감자 썰기')")
    start_time: str = Field(..., description="단계 시작 시각 'MM:SS'")
    end_time: str = Field(..., description="단계 종료 시각 'MM:SS'")
    gesture: str = Field(..., description="제스처명 (썰기/굽기/볶기/젓기)")
