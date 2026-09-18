"""化粪池清掏与排污外运记录模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CleaningRecord(Base):
    """一次化粪池清掏作业，登记清掏量与排污外运去向。"""

    __tablename__ = "cleaning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    clean_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="清掏时间"
    )
    operator_unit: Mapped[str] = mapped_column(String(120), comment="作业单位")
    volume: Mapped[float] = mapped_column(Float, comment="清掏量（立方米）")
    destination: Mapped[str] = mapped_column(String(200), comment="排污外运去向")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    restroom: Mapped["Restroom"] = relationship(back_populates="cleanings")  # noqa: F821
