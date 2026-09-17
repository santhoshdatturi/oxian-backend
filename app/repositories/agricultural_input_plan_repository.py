from typing import List, Optional

from app.infrastructure.database.collections import (
    get_agricultural_input_plans_collection,
)
from app.schemas.agricultural_input_plan import (
    AgriculturalInputPlan,
    AgriculturalInputPlanDocument,
    AgriculturalInputPlanInvariantFields,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_agricultural_input_plan(
    document: dict,
    language: PersistenceLanguage,
) -> AgriculturalInputPlan:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in AgriculturalInputPlanInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = AgriculturalInputPlanInvariantFields.model_validate(invariant_data)
    return AgriculturalInputPlan.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


async def create(
    plan: AgriculturalInputPlanDocument,
) -> AgriculturalInputPlanDocument:
    await get_agricultural_input_plans_collection().insert_one(
        plan.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return plan


async def get_by_id(
    plan_id: str,
    language: PersistenceLanguage = PersistenceLanguage.USER_LANGUAGE,
) -> Optional[AgriculturalInputPlan]:
    doc = await get_agricultural_input_plans_collection().find_one({"_id": plan_id})
    if not doc:
        return None
    return _to_agricultural_input_plan(doc, language)


async def list_by_crop(
    crop_id: str,
    language: PersistenceLanguage = PersistenceLanguage.USER_LANGUAGE,
    limit: int = 100,
) -> List[AgriculturalInputPlan]:
    cursor = (
        get_agricultural_input_plans_collection()
        .find({"cultivation_crop_id": crop_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_to_agricultural_input_plan(doc, language) for doc in docs]


async def save(
    plan: AgriculturalInputPlanDocument,
) -> AgriculturalInputPlanDocument:
    await get_agricultural_input_plans_collection().replace_one(
        {"_id": plan.id},
        plan.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return plan
