from pydantic import BaseModel, Field


class VideoSearchOut(BaseModel):
    """YouTube 검색 결과 1건."""

    videoId: str = Field(..., description="YouTube 영상 ID")
    title: str = Field(..., description="영상 제목")
    thumbnail: str = Field(..., description="썸네일 이미지 URL")
    channelTitle: str = Field(..., description="채널명")
