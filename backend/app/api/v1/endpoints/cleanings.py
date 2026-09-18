"""化粪池清掏与排污外运接口。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.cleaning import (
    CleaningCreate,
    CleaningOut,
    CleaningScheduleItem,
    CleaningUpdate,
)
from app.schemas.common import MessageOut, Page
from app.services import cleaning_service

router = APIRouter(prefix="/cleanings", tags=["化粪池清掏"])


@router.get("", response_model=Page[CleaningOut], summary="清掏记录列表")
def list_cleanings(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    operator_unit: Annotated[str | None, Query(description="作业单位")] = None,
    keyword: Annotated[str | None, Query(description="作业单位/去向/公厕名称模糊搜索")] = None,
    date_from: Annotated[date | None, Query(description="开始日期")] = None,
    date_to: Annotated[date | None, Query(description="结束日期")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "clean_time",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[CleaningOut]:
    rows, total = cleaning_service.list_cleanings(
        db,
        restroom_id=restroom_id,
        district=district,
        operator_unit=operator_unit,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[CleaningOut](
        items=[cleaning_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=CleaningOut, status_code=201, summary="登记清掏记录")
def create_cleaning(
    payload: CleaningCreate, db: Annotated[Session, Depends(get_db)]
) -> CleaningOut:
    return cleaning_service.to_out(cleaning_service.create_cleaning(db, payload))


@router.get("/schedule", response_model=list[CleaningScheduleItem], summary="清掏周期推算与到期提醒")
def get_schedule(
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query(description="按清掏状态过滤：正常/临期/已超期/未设置")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    keyword: Annotated[str | None, Query(description="公厕名称/编号模糊搜索")] = None,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
) -> list[CleaningScheduleItem]:
    return cleaning_service.list_schedule(
        db, status=status, district=district, keyword=keyword, restroom_id=restroom_id
    )


@router.get("/{cleaning_id}", response_model=CleaningOut, summary="清掏记录详情")
def get_cleaning(cleaning_id: int, db: Annotated[Session, Depends(get_db)]) -> CleaningOut:
    return cleaning_service.to_out(cleaning_service.get_cleaning(db, cleaning_id))


@router.patch("/{cleaning_id}", response_model=CleaningOut, summary="更新清掏记录")
def update_cleaning(
    cleaning_id: int, payload: CleaningUpdate, db: Annotated[Session, Depends(get_db)]
) -> CleaningOut:
    return cleaning_service.to_out(cleaning_service.update_cleaning(db, cleaning_id, payload))


@router.delete("/{cleaning_id}", response_model=MessageOut, summary="删除清掏记录")
def delete_cleaning(
    cleaning_id: int, db: Annotated[Session, Depends(get_db)]
) -> MessageOut:
    cleaning_service.delete_cleaning(db, cleaning_id)
    return MessageOut(message="删除成功")
