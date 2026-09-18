"""化粪池清掏与排污外运台账相关数据结构。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.restroom import RestroomBrief


class SepticCleaningBase(BaseModel):
    clean_date: date = Field(description="清掏日期")
    contractor: str = Field(min_length=1, max_length=120, description="作业单位")
    volume: float = Field(gt=0, le=10000, description="清掏量（立方米）")
    destination: str = Field(min_length=1, max_length=200, description="外运去向（处理场站）")
    vehicle_no: str = Field(default="", max_length=30, description="运输车牌号")
    manifest_no: str = Field(default="", max_length=60, description="联单编号")
    operator: str = Field(default="", max_length=60, description="现场负责人")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class SepticCleaningCreate(SepticCleaningBase):
    restroom_id: int = Field(description="所属公厕")


class SepticCleaningUpdate(BaseModel):
    """局部更新，仅提交需要变更的字段。"""

    clean_date: date | None = None
    contractor: str | None = Field(default=None, min_length=1, max_length=120)
    volume: float | None = Field(default=None, gt=0, le=10000)
    destination: str | None = Field(default=None, min_length=1, max_length=200)
    vehicle_no: str | None = Field(default=None, max_length=30)
    manifest_no: str | None = Field(default=None, max_length=60)
    operator: str | None = Field(default=None, max_length=60)
    remark: str | None = Field(default=None, max_length=500)


class SepticCleaningOut(SepticCleaningBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    restroom_id: int
    restroom: RestroomBrief | None = None
    created_at: datetime
    updated_at: datetime


class SepticSchedule(BaseModel):
    """单座公厕的清掏计划与预警状态。"""

    restroom: RestroomBrief
    septic_capacity: float
    usage_frequency: str
    cycle_days: int = Field(description="生效清掏周期（天）：人工设置优先，否则按池容/频次推算")
    cycle_overridden: bool = Field(description="是否人工指定了清掏周期")
    latest_clean_date: date | None = None
    next_clean_date: date | None = None
    days_remaining: int | None = Field(default=None, description="距下次清掏天数，负数表示已超期")
    cleaning_count: int = 0
    latest_volume: float | None = None
    status: str = Field(description="正常 / 即将到期 / 已超期 / 未建档")


class SepticOverview(BaseModel):
    """化粪池清掏看板指标。"""

    restroom_total: int = 0
    cleaning_total: int = 0
    cleaning_month: int = Field(default=0, description="本月清掏作业次数")
    volume_month: float = Field(default=0.0, description="本月清掏量合计（立方米）")
    overdue_count: int = 0
    due_soon_count: int = 0
