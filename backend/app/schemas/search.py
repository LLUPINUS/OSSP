from pydantic import BaseModel, Field


class VideoSearchOut(BaseModel):
    """YouTube 검색 결과 1건."""

    videoId: str = Field(..., description="YouTube 영상 ID")
    title: str = Field(..., description="영상 제목")
    thumbnail: str = Field(..., description="썸네일 이미지 URL")
    channelTitle: str = Field(..., description="채널명")
    duration: str | None = Field(None, description="영상 길이 'M:SS'/'H:MM:SS' (videos.list 2차 호출, 없으면 null)")
    viewCount: str | None = Field(None, description="조회수 한국어 축약 (예: '1.2만회', 없으면 null)")


class SearchPageOut(BaseModel):
    """YouTube 검색 결과 페이지."""

    items: list[VideoSearchOut]
    nextPageToken: str | None = None
