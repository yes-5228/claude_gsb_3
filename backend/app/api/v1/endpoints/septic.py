"""化粪池清掏与排污外运台账接口。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.septic import (
    SepticCleaningCreate,
    SepticCleaningOut,
    SepticCleaningUpdate,
    SepticOverview,
    SepticSchedule,
)
from app.services import septic_service

router = APIRouter(prefix="/septic", tags=["化粪池清掏"])


@router.get("/overview", response_model=SepticOverview, summary="清掏台账指标")
def get_overview(db: Annotated[Session, Depends(get_db)]) -> SepticOverview:
    return septic_service.overview(db)


@router.get("/schedules", response_model=list[SepticSchedule], summary="公厕清掏计划与到期预警")
def list_schedules(
    db: Annotated[Session, Depends(get_db)],
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    status: Annotated[str | None, Query(description="计划状态：正常/即将到期/已超期/未建档")] = None,
    overdue_only: Annotated[bool, Query(description="仅看超期未清掏的公厕")] = False,
    keyword: Annotated[str | None, Query(description="公厕名称/编号/地址模糊搜索")] = None,
) -> list[SepticSchedule]:
    schedules = septic_service.list_schedules(db, district=district, status=status, keyword=keyword)
    if overdue_only:
        schedules = [item for item in schedules if item.status == "已超期"]
    return schedules


@router.get("/cleanings", response_model=Page[SepticCleaningOut], summary="清掏外运台账列表")
def list_cleanings(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    contractor: Annotated[str | None, Query(description="按作业单位过滤")] = None,
    destination: Annotated[str | None, Query(description="按外运去向过滤")] = None,
    keyword: Annotated[str | None, Query(description="编号/单位/去向/车牌/联单模糊搜索")] = None,
    date_from: Annotated[date | None, Query(description="清掏开始日期")] = None,
    date_to: Annotated[date | None, Query(description="清掏结束日期")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "clean_date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[SepticCleaningOut]:
    rows, total = septic_service.list_cleanings(
        db,
        restroom_id=restroom_id,
        district=district,
        contractor=contractor,
        destination=destination,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[SepticCleaningOut](
        items=[septic_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("/cleanings", response_model=SepticCleaningOut, status_code=201, summary="登记清掏记录")
def create_cleaning(
    payload: SepticCleaningCreate, db: Annotated[Session, Depends(get_db)]
) -> SepticCleaningOut:
    return septic_service.to_out(septic_service.create_cleaning(db, payload))


@router.get("/cleanings/{cleaning_id}", response_model=SepticCleaningOut, summary="清掏记录详情")
def get_cleaning(cleaning_id: int, db: Annotated[Session, Depends(get_db)]) -> SepticCleaningOut:
    return septic_service.to_out(septic_service.get_cleaning(db, cleaning_id))


@router.patch("/cleanings/{cleaning_id}", response_model=SepticCleaningOut, summary="更新清掏记录")
def update_cleaning(
    cleaning_id: int, payload: SepticCleaningUpdate, db: Annotated[Session, Depends(get_db)]
) -> SepticCleaningOut:
    return septic_service.to_out(septic_service.update_cleaning(db, cleaning_id, payload))


@router.delete("/cleanings/{cleaning_id}", response_model=MessageOut, summary="删除清掏记录")
def delete_cleaning(cleaning_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    septic_service.delete_cleaning(db, cleaning_id)
    return MessageOut(message="删除成功")
