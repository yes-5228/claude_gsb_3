"""化粪池清掏与排污外运台账业务逻辑。"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    SEPTIC_CYCLE_CAPACITY_FACTOR,
    SEPTIC_CYCLE_MAX_DAYS,
    SEPTIC_CYCLE_MIN_DAYS,
    SEPTIC_REMIND_BEFORE_DAYS,
    SEPTIC_STATUS_DUE_SOON,
    SEPTIC_STATUS_NORMAL,
    SEPTIC_STATUS_OVERDUE,
    SEPTIC_STATUS_UNKNOWN,
    USAGE_LOAD_FACTORS,
)
from app.core.exceptions import NotFoundError
from app.models import Restroom, SepticCleaning
from app.schemas.restroom import RestroomBrief
from app.schemas.septic import SepticCleaningCreate, SepticCleaningOut, SepticOverview, SepticSchedule

SORTABLE_FIELDS = {
    "clean_date": SepticCleaning.clean_date,
    "volume": SepticCleaning.volume,
    "created_at": SepticCleaning.created_at,
    "code": SepticCleaning.code,
}


def _next_code(db: Session, clean_date: date) -> str:
    """生成形如 HC-20260918-001 的清掏记录编号，按清掏日期取当日流水号。"""
    prefix = f"HC-{clean_date.strftime('%Y%m%d')}"
    seq = (
        db.scalar(
            select(func.count()).select_from(SepticCleaning).where(SepticCleaning.code.like(f"{prefix}-%"))
        )
        or 0
    ) + 1
    while True:
        code = f"{prefix}-{seq:03d}"
        if not db.scalar(select(SepticCleaning.id).where(SepticCleaning.code == code)):
            return code
        seq += 1


def calc_cycle_days(restroom: Restroom) -> int:
    """推算清掏周期（天）：人工设置优先，否则按池容与使用频次估算并夹取到上下限。"""
    if restroom.septic_cycle_days:
        return int(restroom.septic_cycle_days)
    load = USAGE_LOAD_FACTORS.get(restroom.usage_frequency, 1.0)
    raw = (restroom.septic_capacity or 0) * SEPTIC_CYCLE_CAPACITY_FACTOR / load
    return max(SEPTIC_CYCLE_MIN_DAYS, min(SEPTIC_CYCLE_MAX_DAYS, round(raw)))


def effective_cycle_days(septic_capacity: float, usage_frequency: str, cycle_days: int | None) -> int:
    """与 ORM 无关的周期推算，供只拿到字段值的调用方使用。"""
    if cycle_days:
        return int(cycle_days)
    load = USAGE_LOAD_FACTORS.get(usage_frequency, 1.0)
    raw = (septic_capacity or 0) * SEPTIC_CYCLE_CAPACITY_FACTOR / load
    return max(SEPTIC_CYCLE_MIN_DAYS, min(SEPTIC_CYCLE_MAX_DAYS, round(raw)))


def get_cleaning(db: Session, cleaning_id: int) -> SepticCleaning:
    cleaning = db.get(SepticCleaning, cleaning_id)
    if cleaning is None:
        raise NotFoundError(f"清掏记录 {cleaning_id} 不存在")
    return cleaning


def to_out(cleaning: SepticCleaning) -> SepticCleaningOut:
    return SepticCleaningOut.model_validate(cleaning)


def list_cleanings(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    contractor: str | None = None,
    destination: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "clean_date",
    order: str = "desc",
) -> tuple[list[SepticCleaning], int]:
    stmt = select(SepticCleaning)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == SepticCleaning.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(SepticCleaning.restroom_id == restroom_id)
    if contractor:
        stmt = stmt.where(SepticCleaning.contractor.like(f"%{contractor.strip()}%"))
    if destination:
        stmt = stmt.where(SepticCleaning.destination.like(f"%{destination.strip()}%"))
    if date_from:
        stmt = stmt.where(SepticCleaning.clean_date >= date_from)
    if date_to:
        stmt = stmt.where(SepticCleaning.clean_date <= date_to)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                SepticCleaning.code.like(like),
                SepticCleaning.contractor.like(like),
                SepticCleaning.destination.like(like),
                SepticCleaning.vehicle_no.like(like),
                SepticCleaning.manifest_no.like(like),
                SepticCleaning.operator.like(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, SepticCleaning.clean_date)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), SepticCleaning.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def latest_cleaning(db: Session, restroom_id: int) -> SepticCleaning | None:
    return db.scalars(
        select(SepticCleaning)
        .where(SepticCleaning.restroom_id == restroom_id)
        .order_by(SepticCleaning.clean_date.desc(), SepticCleaning.id.desc())
        .limit(1)
    ).first()


def create_cleaning(db: Session, payload: SepticCleaningCreate) -> SepticCleaning:
    restroom = db.get(Restroom, payload.restroom_id)
    if restroom is None:
        raise NotFoundError(f"公厕 {payload.restroom_id} 不存在")
    cleaning = SepticCleaning(
        code=_next_code(db, payload.clean_date),
        **payload.model_dump(),
    )
    db.add(cleaning)
    db.commit()
    db.refresh(cleaning)
    restroom.updated_at = datetime.now()
    db.commit()
    return cleaning


def update_cleaning(db: Session, cleaning_id: int, payload) -> SepticCleaning:
    cleaning = get_cleaning(db, cleaning_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cleaning, key, value)
    db.commit()
    db.refresh(cleaning)
    return cleaning


def delete_cleaning(db: Session, cleaning_id: int) -> None:
    cleaning = get_cleaning(db, cleaning_id)
    db.delete(cleaning)
    db.commit()


def build_schedule(
    restroom: Restroom,
    latest: SepticCleaning | None,
    *,
    cleaning_count: int = 0,
    today: date | None = None,
) -> SepticSchedule:
    """计算单座公厕的清掏计划状态。"""
    today = today or date.today()
    cycle_days = calc_cycle_days(restroom)

    if latest is None:
        status = SEPTIC_STATUS_UNKNOWN
        next_clean_date = None
        days_remaining = None
        latest_volume = None
        latest_date = None
    else:
        latest_date = latest.clean_date
        next_clean_date = latest_date + timedelta(days=cycle_days)
        days_remaining = (next_clean_date - today).days
        latest_volume = latest.volume
        if days_remaining < 0:
            status = SEPTIC_STATUS_OVERDUE
        elif days_remaining <= SEPTIC_REMIND_BEFORE_DAYS:
            status = SEPTIC_STATUS_DUE_SOON
        else:
            status = SEPTIC_STATUS_NORMAL

    return SepticSchedule(
        restroom=RestroomBrief.model_validate(restroom),
        septic_capacity=restroom.septic_capacity,
        usage_frequency=restroom.usage_frequency,
        cycle_days=cycle_days,
        cycle_overridden=bool(restroom.septic_cycle_days),
        latest_clean_date=latest_date,
        next_clean_date=next_clean_date,
        days_remaining=days_remaining,
        cleaning_count=cleaning_count,
        latest_volume=latest_volume,
        status=status,
    )


def list_schedules(
    db: Session,
    *,
    district: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> list[SepticSchedule]:
    """全部公厕的清掏计划，默认按紧急程度（超期优先、剩余天数升序）排列。"""
    stmt = select(Restroom).order_by(Restroom.id)
    if district:
        stmt = stmt.where(Restroom.district == district)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(Restroom.name.like(like), Restroom.code.like(like), Restroom.address.like(like))
        )

    today = date.today()

    # 一次性取每座公厕最近一次清掏日期与累计次数，避免逐条查询
    agg_rows = db.execute(
        select(
            SepticCleaning.restroom_id,
            func.max(SepticCleaning.clean_date),
            func.count(SepticCleaning.id),
        ).group_by(SepticCleaning.restroom_id)
    ).all()
    latest_dates: dict[int, date] = {}
    count_map: dict[int, int] = {}
    for restroom_id, latest_date, total in agg_rows:
        latest_dates[restroom_id] = latest_date
        count_map[restroom_id] = int(total)

    schedules: list[SepticSchedule] = []
    for restroom in db.scalars(stmt):
        latest_date = latest_dates.get(restroom.id)
        latest = None
        if latest_date is not None:
            latest = db.scalars(
                select(SepticCleaning)
                .where(
                    SepticCleaning.restroom_id == restroom.id,
                    SepticCleaning.clean_date == latest_date,
                )
                .order_by(SepticCleaning.id.desc())
                .limit(1)
            ).first()
        schedule = build_schedule(
            restroom, latest, cleaning_count=count_map.get(restroom.id, 0), today=today
        )
        schedules.append(schedule)

    status_rank = {
        SEPTIC_STATUS_OVERDUE: 0,
        SEPTIC_STATUS_UNKNOWN: 1,
        SEPTIC_STATUS_DUE_SOON: 2,
        SEPTIC_STATUS_NORMAL: 3,
    }
    schedules.sort(
        key=lambda item: (
            status_rank.get(item.status, 9),
            item.days_remaining if item.days_remaining is not None else 10**6,
        )
    )
    if status:
        schedules = [item for item in schedules if item.status == status]
    return schedules


def overview(db: Session) -> SepticOverview:
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

    schedules = list_schedules(db)
    month_rows = db.execute(
        select(func.count(), func.coalesce(func.sum(SepticCleaning.volume), 0.0)).where(
            SepticCleaning.clean_date >= month_start,
            SepticCleaning.clean_date <= month_end,
        )
    ).one()

    return SepticOverview(
        restroom_total=len(schedules),
        cleaning_total=db.scalar(select(func.count()).select_from(SepticCleaning)) or 0,
        cleaning_month=int(month_rows[0] or 0),
        volume_month=round(float(month_rows[1] or 0.0), 2),
        overdue_count=sum(1 for item in schedules if item.status == SEPTIC_STATUS_OVERDUE),
        due_soon_count=sum(1 for item in schedules if item.status == SEPTIC_STATUS_DUE_SOON),
    )


def restroom_septic_summary(db: Session, restroom: Restroom) -> dict:
    """公厕详情页用的化粪池汇总字段。"""
    count, latest_date = db.execute(
        select(func.count(SepticCleaning.id), func.max(SepticCleaning.clean_date)).where(
            SepticCleaning.restroom_id == restroom.id
        )
    ).one()
    latest = None
    if latest_date is not None:
        latest = db.scalars(
            select(SepticCleaning)
            .where(
                SepticCleaning.restroom_id == restroom.id,
                SepticCleaning.clean_date == latest_date,
            )
            .order_by(SepticCleaning.id.desc())
            .limit(1)
        ).first()
    schedule = build_schedule(restroom, latest, cleaning_count=int(count or 0))
    return {
        "septic_cycle_actual": schedule.cycle_days,
        "latest_clean_date": schedule.latest_clean_date,
        "next_clean_date": schedule.next_clean_date,
        "cleaning_count": int(count or 0),
    }
