from datetime import date, datetime, timedelta
from typing import Any

from app.core.errors import (
    CultivationCropNotFound,
    CultivationTaskNotFound,
    FarmProfileNotFound,
    TaskAlreadyCompleted,
    TaskNotSkippable,
)
from app.repositories import (
    cultivation_task_repository,
    investment_breakdown_repository,
)
from app.schemas.cultivation_task import (
    CreateCultivationTaskInput,
    CultivationTask,
    CultivationTaskDocument,
    InvestmentActualCostInput,
    ReschedulePreviewResponse,
    TaskShiftPreview,
    TaskState,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import cultivation_crop_service, farm_profile_service


async def list_cultivation_tasks(
    *, crop_id: str, user_id: str, limit: int = 100
) -> list[CultivationTask]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    return await cultivation_task_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def get_cultivation_task(*, task_id: str, user_id: str) -> CultivationTask | None:
    crop_id = await cultivation_task_repository.get_crop_id_by_id(task_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return None
    return await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def complete_cultivation_task(
    *,
    task_id: str,
    user_id: str,
    execution_notes: str | None = None,
    actual_costs: list[InvestmentActualCostInput] | None = None,
    completed_at: datetime | None = None,
    crop_id: str | None = None,
) -> CultivationTask:
    resolved_crop_id = crop_id or await cultivation_task_repository.get_crop_id_by_id(
        task_id
    )
    if not resolved_crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=resolved_crop_id
    ):
        raise CultivationTaskNotFound(task_id)

    task = await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=resolved_crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    if task is None:
        raise CultivationTaskNotFound(task_id)

    if task.status == TaskState.COMPLETED:
        raise TaskAlreadyCompleted(task_id)

    completed_task = await cultivation_task_repository.complete_task(
        task_id=task_id,
        crop_id=resolved_crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        completed_at=completed_at,
        execution_notes=execution_notes,
        actual_costs=actual_costs,
    )
    if completed_task is None:
        raise CultivationTaskNotFound(task_id)

    # Roll up actual costs into crop's investment breakdown if actual_costs were submitted
    if actual_costs:
        await investment_breakdown_repository.record_actual_costs(
            crop_id=resolved_crop_id,
            actual_costs=actual_costs,
        )

    return completed_task


async def skip_cultivation_task(
    *,
    task_id: str,
    user_id: str,
    reason: str | None = None,
    crop_id: str | None = None,
) -> CultivationTask:
    resolved_crop_id = crop_id or await cultivation_task_repository.get_crop_id_by_id(
        task_id
    )
    if not resolved_crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=resolved_crop_id
    ):
        raise CultivationTaskNotFound(task_id)

    task = await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=resolved_crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    if task is None:
        raise CultivationTaskNotFound(task_id)

    if not task.skippable:
        raise TaskNotSkippable(task_id)

    skipped_task = await cultivation_task_repository.skip_task(
        task_id=task_id,
        crop_id=resolved_crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        reason=reason,
    )
    if skipped_task is None:
        raise CultivationTaskNotFound(task_id)

    return skipped_task


async def add_custom_task(
    *,
    crop_id: str,
    user_id: str,
    task_input: CreateCultivationTaskInput,
) -> CultivationTask:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)

    return await cultivation_task_repository.add_custom_task(
        crop_id=crop_id,
        task_input=task_input,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def list_farm_calendar_tasks(
    *,
    farm_id: str,
    user_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    status: TaskState | None = None,
    limit: int = 100,
) -> list[CultivationTask]:
    if not await farm_profile_service.has_farm_access(farm_id=farm_id, user_id=user_id):
        raise FarmProfileNotFound(farm_id)

    crops = await cultivation_crop_service.list_cultivation_crops(
        user_id=user_id,
        farm_id=farm_id,
        limit=100,
    )
    crop_ids = [crop.id for crop in crops]
    return await cultivation_task_repository.list_by_crops(
        crop_ids=crop_ids,
        language=PersistenceLanguage.USER_LANGUAGE,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )


async def delete_cultivation_task(*, task_id: str, user_id: str) -> bool:
    crop_id = await cultivation_task_repository.get_crop_id_by_id(task_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return False
    return await cultivation_task_repository.delete(task_id=task_id, crop_id=crop_id)


async def _list_cultivation_tasks(
    crop_id: str, limit: int = 100
) -> list[CultivationTask]:
    return await cultivation_task_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
        limit=limit,
    )


async def _get_cultivation_task(
    task_id: str, crop_id: str | None = None
) -> CultivationTask | None:
    return await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_cultivation_task(
    document: CultivationTaskDocument,
) -> CultivationTaskDocument:
    return await cultivation_task_repository.create(document)


async def preview_reschedule(
    *, crop_id: str, user_id: str
) -> ReschedulePreviewResponse:
    """Preview date shifts for overdue pending tasks and later scheduled work.

    Included overdue tasks restart today while included non-overdue tasks move by
    the delay measured from the earliest overdue task's end date.

    Raises:
        CultivationCropNotFound: If the user cannot access the crop.
    """
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)

    tasks = await cultivation_task_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=200,
    )
    today = date.today()
    pending_tasks = [t for t in tasks if t.status == TaskState.PENDING]
    overdue_tasks = [t for t in pending_tasks if t.planned_end_date < today]

    if not overdue_tasks:
        return ReschedulePreviewResponse(
            crop_id=crop_id,
            days_delayed=0,
            overdue_task_count=0,
            tasks_to_reschedule=[],
        )

    earliest_overdue = min(overdue_tasks, key=lambda t: t.planned_end_date)
    days_delayed = max((today - earliest_overdue.planned_end_date).days, 1)

    shifts: list[TaskShiftPreview] = []
    for task in pending_tasks:
        if task.planned_end_date < earliest_overdue.planned_start_date and task.planned_end_date >= today:
            continue
        if task.planned_end_date < earliest_overdue.planned_end_date and task.planned_end_date < today:
            # Also overdue, will be rescheduled
            pass
        elif task.planned_end_date < earliest_overdue.planned_start_date:
            continue

        duration = task.planned_end_date - task.planned_start_date
        is_od = task.planned_end_date < today
        if is_od:
            # Overdue task starts today
            prop_start = today
            prop_end = today + duration
        else:
            # Shift subsequent dependent tasks by delay_days
            prop_start = task.planned_start_date + timedelta(days=days_delayed)
            prop_end = task.planned_end_date + timedelta(days=days_delayed)

        shifts.append(
            TaskShiftPreview(
                task_id=task.id,
                task_name=task.task_name,
                current_start_date=task.planned_start_date,
                current_end_date=task.planned_end_date,
                proposed_start_date=prop_start,
                proposed_end_date=prop_end,
                is_overdue=is_od,
            )
        )

    return ReschedulePreviewResponse(
        crop_id=crop_id,
        days_delayed=days_delayed,
        overdue_task_count=len(overdue_tasks),
        tasks_to_reschedule=shifts,
    )


async def confirm_reschedule(
    *,
    crop_id: str,
    user_id: str,
    task_ids: list[str] | None = None,
) -> list[CultivationTask]:
    preview = await preview_reschedule(crop_id=crop_id, user_id=user_id)
    if not preview.tasks_to_reschedule:
        return []

    target_shifts = preview.tasks_to_reschedule
    if task_ids:
        id_set = set(task_ids)
        target_shifts = [s for s in target_shifts if s.task_id in id_set]

    rescheduled: list[CultivationTask] = []
    for shift in target_shifts:
        await cultivation_task_repository.update_task_dates(
            task_id=shift.task_id,
            planned_start_date=shift.proposed_start_date,
            planned_end_date=shift.proposed_end_date,
            status=TaskState.RE_SCHEDULED,
        )
        updated = await cultivation_task_repository.get_by_id(
            task_id=shift.task_id,
            language=PersistenceLanguage.USER_LANGUAGE,
            crop_id=crop_id,
        )
        if updated:
            rescheduled.append(updated)

    return rescheduled


async def check_all_overdue_tasks() -> dict[str, Any]:
    today = date.today()
    overdue_docs = await cultivation_task_repository.list_pending_overdue_tasks(
        as_of_date=today,
        limit=500,
    )
    crop_ids = list({doc["crop_id"] for doc in overdue_docs if doc.get("crop_id")})
    return {
        "overdue_tasks_count": len(overdue_docs),
        "affected_crops_count": len(crop_ids),
        "affected_crop_ids": crop_ids,
    }

