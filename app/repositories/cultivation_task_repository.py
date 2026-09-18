from datetime import date, datetime, timezone

from app.infrastructure.database.collections import get_cultivation_tasks_collection
from app.schemas.cultivation_task import (
    CreateCultivationTaskInput,
    CultivationTask,
    CultivationTaskDocument,
    CultivationTaskInvariantFields,
    CultivationTaskTranslatableFields,
    InvestmentActualCostInput,
    TaskState,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_cultivation_task(
    document: dict,
    language: PersistenceLanguage,
) -> CultivationTask:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in CultivationTaskInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = CultivationTaskInvariantFields.model_validate(invariant_data)
    return CultivationTask.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


async def create(task: CultivationTaskDocument) -> CultivationTaskDocument:
    await get_cultivation_tasks_collection().insert_one(
        task.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return task


async def save(task: CultivationTaskDocument) -> CultivationTaskDocument:
    await get_cultivation_tasks_collection().replace_one(
        {"_id": task.id},
        task.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return task


async def save_language(
    task: CultivationTask,
    language: PersistenceLanguage,
) -> CultivationTask:
    translatable_fields = CultivationTaskTranslatableFields.model_validate(
        task
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = CultivationTaskInvariantFields.model_validate(task).model_dump(
        exclude_none=True, mode="json"
    )
    await get_cultivation_tasks_collection().update_one(
        {"_id": task.id, "crop_id": task.crop_id},
        {
            "$set": {
                **invariant_fields,
                language.value: translatable_fields,
            },
        },
        upsert=True,
    )
    return task


async def get_by_id(
    task_id: str,
    language: PersistenceLanguage,
    crop_id: str | None = None,
) -> CultivationTask | None:
    """Return a localized task matching the ID and optional crop."""
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    projection = {
        "_id": 1,
        "crop_id": 1,
        "planned_start_date": 1,
        "planned_end_date": 1,
        "status": 1,
        "priority": 1,
        "skippable": 1,
        "completed_at": 1,
        language.value: 1,
    }
    document = await get_cultivation_tasks_collection().find_one(query, projection)
    if not document:
        return None
    return _to_cultivation_task(document, language)


async def get_document_by_id(
    task_id: str,
    crop_id: str | None = None,
) -> CultivationTaskDocument | None:
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    document = await get_cultivation_tasks_collection().find_one(query)
    if not document:
        return None
    return CultivationTaskDocument.model_validate(document)


async def get_crop_id_by_id(task_id: str) -> str | None:
    document = await get_cultivation_tasks_collection().find_one(
        {"_id": task_id},
        {"crop_id": 1},
    )
    if not document:
        return None
    return document.get("crop_id")


async def list_by_crop(
    crop_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[CultivationTask]:
    """Return the crop's tasks ordered by planned start date."""
    projection = {
        "_id": 1,
        "crop_id": 1,
        "planned_start_date": 1,
        "planned_end_date": 1,
        "status": 1,
        "priority": 1,
        "skippable": 1,
        "completed_at": 1,
        language.value: 1,
    }
    cursor = (
        get_cultivation_tasks_collection()
        .find({"crop_id": crop_id}, projection)
        .sort("planned_start_date", 1)
        .limit(limit)
    )
    return [_to_cultivation_task(document, language) async for document in cursor]


async def delete(task_id: str, crop_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    result = await get_cultivation_tasks_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_crop(crop_id: str) -> int:
    result = await get_cultivation_tasks_collection().delete_many({"crop_id": crop_id})
    return result.deleted_count


async def complete_task(
    task_id: str,
    language: PersistenceLanguage,
    completed_at: datetime | None = None,
    execution_notes: str | None = None,
    actual_costs: list[InvestmentActualCostInput] | None = None,
    crop_id: str | None = None,
) -> CultivationTask | None:
    doc = await get_document_by_id(task_id, crop_id=crop_id)
    if not doc:
        return None

    completion_time = completed_at or datetime.now(timezone.utc)
    doc.status = TaskState.COMPLETED
    doc.completed_at = completion_time

    if execution_notes:
        note_text = f"Execution Notes: {execution_notes}"
        doc.english.notes = (
            f"{doc.english.notes}\n{note_text}" if doc.english.notes else note_text
        )
        doc.user_language.notes = (
            f"{doc.user_language.notes}\n{note_text}"
            if doc.user_language.notes
            else note_text
        )

    if actual_costs:
        for cost_input in actual_costs:
            matched_en = False
            for inv in doc.english.investments:
                if (
                    inv.reason.lower() == cost_input.reason.lower()
                    or inv.category == cost_input.category
                ):
                    inv.actual_cost = cost_input.actual_cost
                    matched_en = True
                    break
            if not matched_en and doc.english.investments:
                doc.english.investments[0].actual_cost = cost_input.actual_cost

            matched_user = False
            for inv in doc.user_language.investments:
                if (
                    inv.reason.lower() == cost_input.reason.lower()
                    or inv.category == cost_input.category
                ):
                    inv.actual_cost = cost_input.actual_cost
                    matched_user = True
                    break
            if not matched_user and doc.user_language.investments:
                doc.user_language.investments[0].actual_cost = cost_input.actual_cost

    await save(doc)
    return _to_cultivation_task(doc.model_dump(by_alias=True, mode="json"), language)


async def skip_task(
    task_id: str,
    language: PersistenceLanguage,
    reason: str | None = None,
    crop_id: str | None = None,
) -> CultivationTask | None:
    doc = await get_document_by_id(task_id, crop_id=crop_id)
    if not doc:
        return None

    doc.status = TaskState.SKIPPED
    if reason:
        skip_text = f"Skipped Reason: {reason}"
        doc.english.notes = (
            f"{doc.english.notes}\n{skip_text}" if doc.english.notes else skip_text
        )
        doc.user_language.notes = (
            f"{doc.user_language.notes}\n{skip_text}"
            if doc.user_language.notes
            else skip_text
        )

    await save(doc)
    return _to_cultivation_task(doc.model_dump(by_alias=True, mode="json"), language)


async def add_custom_task(
    crop_id: str,
    task_input: CreateCultivationTaskInput,
    language: PersistenceLanguage,
) -> CultivationTask:
    """Create a pending task with the supplied dates and task content."""
    task_doc = CultivationTaskDocument(
        crop_id=crop_id,
        planned_start_date=task_input.planned_start_date,
        planned_end_date=task_input.planned_end_date,
        status=TaskState.PENDING,
        priority=task_input.priority,
        skippable=task_input.skippable,
        english=CultivationTaskTranslatableFields(
            task_name=task_input.task_name,
            description=task_input.description,
            notes=task_input.notes,
            investments=task_input.investments,
        ),
        user_language=CultivationTaskTranslatableFields(
            task_name=task_input.task_name,
            description=task_input.description,
            notes=task_input.notes,
            investments=task_input.investments,
        ),
    )
    await create(task_doc)
    return _to_cultivation_task(
        task_doc.model_dump(by_alias=True, mode="json"), language
    )


async def list_by_crops(
    crop_ids: list[str],
    language: PersistenceLanguage,
    start_date: date | None = None,
    end_date: date | None = None,
    status: TaskState | None = None,
    limit: int = 100,
) -> list[CultivationTask]:
    """Return date-ordered tasks that overlap the optional date range."""
    if not crop_ids:
        return []

    query: dict = {"crop_id": {"$in": crop_ids}}
    if start_date:
        query["planned_end_date"] = {"$gte": start_date.isoformat()}
    if end_date:
        query["planned_start_date"] = {"$lte": end_date.isoformat()}
    if status:
        query["status"] = status.value

    projection = {
        "_id": 1,
        "crop_id": 1,
        "planned_start_date": 1,
        "planned_end_date": 1,
        "status": 1,
        "priority": 1,
        "skippable": 1,
        "completed_at": 1,
        language.value: 1,
    }
    cursor = (
        get_cultivation_tasks_collection()
        .find(query, projection)
        .sort("planned_start_date", 1)
        .limit(limit)
    )
    return [_to_cultivation_task(document, language) async for document in cursor]


async def update_task_dates(
    task_id: str,
    planned_start_date: date,
    planned_end_date: date,
    status: TaskState,
) -> bool:
    res = await get_cultivation_tasks_collection().update_one(
        {"_id": task_id},
        {
            "$set": {
                "planned_start_date": planned_start_date.isoformat(),
                "planned_end_date": planned_end_date.isoformat(),
                "status": status.value,
            }
        },
    )
    return res.modified_count > 0


async def list_pending_overdue_tasks(
    as_of_date: date,
    limit: int = 200,
) -> list[dict]:
    query = {
        "status": TaskState.PENDING.value,
        "planned_end_date": {"$lt": as_of_date.isoformat()},
    }
    cursor = get_cultivation_tasks_collection().find(query).limit(limit)
    return await cursor.to_list(length=limit)

