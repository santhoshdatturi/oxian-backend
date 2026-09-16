from datetime import date, datetime

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
