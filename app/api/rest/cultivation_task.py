from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user_id
from app.schemas.cultivation_task import (
    CompleteTaskRequest,
    CultivationTask,
    SkipTaskRequest,
    TaskState,
)
from app.services import cultivation_task_service

router = APIRouter(tags=["Cultivation Tasks"])


@router.patch(
    "/cultivation-tasks/{task_id}/complete",
    response_model=CultivationTask,
)
async def complete_cultivation_task(
    task_id: str,
    payload: CompleteTaskRequest = CompleteTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    """
    Mark a cultivation task as completed, optionally recording farmer execution notes
    and itemized actual spending.
    """
    return await cultivation_task_service.complete_cultivation_task(
        task_id=task_id,
        user_id=user_id,
        execution_notes=payload.execution_notes,
        actual_costs=payload.actual_costs,
        completed_at=payload.completed_at,
    )


@router.post(
    "/cultivation-tasks/{task_id}/skip",
    response_model=CultivationTask,
)
async def skip_cultivation_task(
    task_id: str,
    payload: SkipTaskRequest = SkipTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    """
    Skip a skippable cultivation task, recording the reason.
    """
    return await cultivation_task_service.skip_cultivation_task(
        task_id=task_id,
        user_id=user_id,
        reason=payload.reason,
    )


@router.get(
    "/farms/{farm_id}/calendar/tasks",
    response_model=list[CultivationTask],
)
async def list_farm_calendar_tasks(
    farm_id: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    status: Optional[TaskState] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationTask]:
    """
    Fetch all scheduled cultivation tasks across all crops on a farm for a given timeframe.
    """
    return await cultivation_task_service.list_farm_calendar_tasks(
        farm_id=farm_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )
