"""化粪池清掏与排污外运台账模型。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SepticCleaning(Base):
    """一次化粪池清掏与排污外运作业记录。"""

    __tablename__ = "septic_cleanings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="清掏记录编号")
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    clean_date: Mapped[date] = mapped_column(Date, index=True, comment="清掏日期")
    contractor: Mapped[str] = mapped_column(String(120), comment="作业单位")
    volume: Mapped[float] = mapped_column(Float, comment="清掏量（立方米）")
    destination: Mapped[str] = mapped_column(String(200), comment="外运去向（处理场站）")
    vehicle_no: Mapped[str] = mapped_column(String(30), default="", comment="运输车牌号")
    manifest_no: Mapped[str] = mapped_column(String(60), default="", comment="联单编号")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="现场负责人")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="cleanings")  # noqa: F821
