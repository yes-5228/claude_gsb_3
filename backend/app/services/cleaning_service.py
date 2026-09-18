"""化粪池清掏与排污外运业务逻辑。"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    CLEAN_CYCLE_MAX_DAYS,
    CLEAN_CYCLE_MIN_DAYS,
    CLEAN_REMIND_DAYS,
    SEWAGE_PER_USE,
    TANK_USABLE_RATIO,
    CleaningStatus,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import CleaningRecord, Restroom
from app.schemas.cleaning import CleaningCreate, CleaningOut, CleaningScheduleItem, CleaningUpdate
from app.services import restroom_service

SORTABLE_FIELDS = {
    "clean_time": CleaningRecord.clean_time,
    "volume": CleaningRecord.volume,
    "operator_unit": CleaningRecord.operator_unit,
    "created_at": CleaningRecord.created_at,
}

# 清掏状态排序权重：超期优先，未设置垫底
_STATUS_RANK = {
    CleaningStatus.OVERDUE.value: 0,
    CleaningStatus.DUE_SOON.value: 1,
    CleaningStatus.NORMAL.value: 2,
    CleaningStatus.UNSET.value: 3,
}


def compute_cycle_days(tank_capacity: float, usage_frequency: int) -> int | None:
    """按池容与使用频次推算清掏周期（天）；缺少基础数据时返回 None。"""
    if not tank_capacity or tank_capacity <= 0 or not usage_frequency or usage_frequency <= 0:
        return None
    daily_volume = usage_frequency * SEWAGE_PER_USE
    days = round(tank_capacity * TANK_USABLE_RATIO / daily_volume)
    return max(CLEAN_CYCLE_MIN_DAYS, min(CLEAN_CYCLE_MAX_DAYS, days))


def build_schedule_item(
    restroom: Restroom,
    *,
    last_clean_time: datetime | None,
    clean_count: int,
    now: datetime | None = None,
) -> CleaningScheduleItem:
    """推算单座公厕的应清日期与到期状态；无清掏记录时自建档时间起算。"""
    now = now or datetime.now()
    cycle_days = compute_cycle_days(restroom.tank_capacity, restroom.usage_frequency)
    next_due_time: datetime | None = None
    days_remaining: int | None = None
    status = CleaningStatus.UNSET.value
    if cycle_days is not None:
        baseline = last_clean_time or restroom.created_at
        next_due_time = baseline + timedelta(days=cycle_days)
        days_remaining = (next_due_time.date() - now.date()).days
        if days_remaining < 0:
            status = CleaningStatus.OVERDUE.value
        elif days_remaining <= CLEAN_REMIND_DAYS:
            status = CleaningStatus.DUE_SOON.value
        else:
            status = CleaningStatus.NORMAL.value
    return CleaningScheduleItem(
        restroom_id=restroom.id,
        code=restroom.code,
        name=restroom.name,
        district=restroom.district,
        tank_capacity=restroom.tank_capacity,
        usage_frequency=restroom.usage_frequency,
        cycle_days=cycle_days,
        clean_count=clean_count,
        last_clean_time=last_clean_time,
        next_due_time=next_due_time,
        days_remaining=days_remaining,
        status=status,
    )


def get_cleaning(db: Session, cleaning_id: int) -> CleaningRecord:
    record = db.get(CleaningRecord, cleaning_id)
    if record is None:
        raise NotFoundError(f"清掏记录 {cleaning_id} 不存在")
    return record


def to_out(record: CleaningRecord) -> CleaningOut:
    return CleaningOut.model_validate(record)


def list_cleanings(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    operator_unit: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "clean_time",
    order: str = "desc",
) -> tuple[list[CleaningRecord], int]:
    stmt = select(CleaningRecord)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == CleaningRecord.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(CleaningRecord.restroom_id == restroom_id)
    if operator_unit:
        stmt = stmt.where(CleaningRecord.operator_unit.like(f"%{operator_unit.strip()}%"))
    if date_from:
        stmt = stmt.where(CleaningRecord.clean_time >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(CleaningRecord.clean_time <= datetime.combine(date_to, time.max))
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                CleaningRecord.operator_unit.like(like),
                CleaningRecord.destination.like(like),
                CleaningRecord.remark.like(like),
                CleaningRecord.restroom_id.in_(
                    select(Restroom.id).where(Restroom.name.like(like))
                ),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, CleaningRecord.clean_time)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), CleaningRecord.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def _check_clean_time(clean_time: datetime) -> None:
    if clean_time > datetime.now():
        raise DomainError("清掏时间不能晚于当前时间")


def create_cleaning(db: Session, payload: CleaningCreate) -> CleaningRecord:
    restroom_service.get_restroom(db, payload.restroom_id)
    clean_time = payload.clean_time or datetime.now()
    _check_clean_time(clean_time)
    record = CleaningRecord(
        restroom_id=payload.restroom_id,
        clean_time=clean_time,
        operator_unit=payload.operator_unit.strip(),
        volume=payload.volume,
        destination=payload.destination.strip(),
        remark=payload.remark,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    restroom_service.touch(db, payload.restroom_id)
    return record


def update_cleaning(db: Session, cleaning_id: int, payload: CleaningUpdate) -> CleaningRecord:
    record = get_cleaning(db, cleaning_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("clean_time") is not None and payload.clean_time is not None:
        _check_clean_time(payload.clean_time)
        record.clean_time = payload.clean_time
    if data.get("operator_unit") is not None and payload.operator_unit is not None:
        record.operator_unit = payload.operator_unit.strip()
    if data.get("volume") is not None and payload.volume is not None:
        record.volume = payload.volume
    if data.get("destination") is not None and payload.destination is not None:
        record.destination = payload.destination.strip()
    if "remark" in data:
        record.remark = payload.remark
    db.commit()
    db.refresh(record)
    return record


def delete_cleaning(db: Session, cleaning_id: int) -> None:
    record = get_cleaning(db, cleaning_id)
    db.delete(record)
    db.commit()


def _clean_stats(db: Session) -> dict[int, tuple[datetime, int]]:
    """各公厕的最近清掏时间与累计次数。"""
    rows = db.execute(
        select(
            CleaningRecord.restroom_id,
            func.max(CleaningRecord.clean_time),
            func.count(CleaningRecord.id),
        ).group_by(CleaningRecord.restroom_id)
    ).all()
    return {rid: (last_time, int(count)) for rid, last_time, count in rows}


def list_schedule(
    db: Session,
    *,
    status: str | None = None,
    district: str | None = None,
    keyword: str | None = None,
    restroom_id: int | None = None,
) -> list[CleaningScheduleItem]:
    """逐公厕推算清掏周期与到期状态，按 超期→临期→正常→未设置 排序。"""
    stmt = select(Restroom)
    if restroom_id:
        stmt = stmt.where(Restroom.id == restroom_id)
    if district:
        stmt = stmt.where(Restroom.district == district)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Restroom.name.like(like), Restroom.code.like(like)))
    restrooms = list(db.scalars(stmt.order_by(Restroom.code)))

    stats = _clean_stats(db)
    now = datetime.now()
    items = []
    for restroom in restrooms:
        last_time, count = stats.get(restroom.id, (None, 0))
        items.append(
            build_schedule_item(restroom, last_clean_time=last_time, clean_count=count, now=now)
        )
    if status:
        items = [item for item in items if item.status == status]
    items.sort(
        key=lambda item: (
            _STATUS_RANK.get(item.status, 9),
            item.days_remaining if item.days_remaining is not None else 99999,
            item.code,
        )
    )
    return items


def reminder_summary(db: Session, *, limit: int = 6) -> tuple[int, int, list[CleaningScheduleItem]]:
    """看板用：超期与临期数量，以及需要提醒的公厕清单（超期优先）。"""
    items = list_schedule(db)
    overdue = sum(1 for item in items if item.status == CleaningStatus.OVERDUE.value)
    due_soon = sum(1 for item in items if item.status == CleaningStatus.DUE_SOON.value)
    reminders = [
        item
        for item in items
        if item.status in (CleaningStatus.OVERDUE.value, CleaningStatus.DUE_SOON.value)
    ][:limit]
    return overdue, due_soon, reminders
