from sqlalchemy import Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.recipe import Recipe


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # 관계
    recipe: Mapped["Recipe"] = relationship(back_populates="transcripts")