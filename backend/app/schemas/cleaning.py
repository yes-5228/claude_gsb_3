"""化粪池清掏与排污外运相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.restroom import RestroomBrief


class CleaningCreate(BaseModel):
    restroom_id: int = Field(description="所属公厕")
    clean_time: datetime | None = Field(default=None, description="清掏时间，留空取当前时间")
    operator_unit: str = Field(min_length=1, max_length=120, description="作业单位")
    volume: float = Field(gt=0, description="清掏量（立方米）")
    destination: str = Field(min_length=1, max_length=200, description="排污外运去向")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class CleaningUpdate(BaseModel):
    """局部更新，仅提交需要变更的字段。"""

    clean_time: datetime | None = None
    operator_unit: str | None = Field(default=None, min_length=1, max_length=120)
    volume: float | None = Field(default=None, gt=0)
    destination: str | None = Field(default=None, min_length=1, max_length=200)
    remark: str | None = Field(default=None, max_length=500)


class CleaningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    clean_time: datetime
    operator_unit: str
    volume: float
    destination: str
    remark: str | None = None
    created_at: datetime


class CleaningScheduleItem(BaseModel):
    """单座公厕的清掏周期推算结果，用于提醒与超期清单。"""

    restroom_id: int
    code: str
    name: str
    district: str
    tank_capacity: float = Field(description="化粪池容积（立方米）")
    usage_frequency: int = Field(description="日均使用频次（人次）")
    cycle_days: int | None = Field(default=None, description="推算清掏周期（天）")
    clean_count: int = Field(default=0, description="累计清掏次数")
    last_clean_time: datetime | None = Field(default=None, description="最近清掏时间")
    next_due_time: datetime | None = Field(default=None, description="下次应清时间")
    days_remaining: int | None = Field(default=None, description="距应清天数，负数表示已超期")
    status: str = Field(description="清掏状态：正常/临期/已超期/未设置")
