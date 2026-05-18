from datetime import datetime
from sqlalchemy import (
    Float, Integer, Text, DateTime, ForeignKey,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.recipe import Recipe
    from app.models.action_label import ActionLabel


class CookingStep(Base):
    __tablename__ = "cooking_steps"
    __table_args__ = (
        UniqueConstraint("recipe_id", "step_order", name="uq_recipe_step_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_label_id: Mapped[int] = mapped_column(
        ForeignKey("action_labels.id"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 관계
    recipe: Mapped["Recipe"] = relationship(back_populates="cooking_steps")
    action_label: Mapped["ActionLabel"] = relationship(back_populates="cooking_steps")