from datetime import datetime, timezone
from typing import List, Optional

from app.infrastructure.database.collections import get_crop_observations_collection
from app.schemas.crop_observation import (
    CropDiagnosisDocument,
    CropDiagnosisResult,
    CropObservation,
    IssueType,
    SeverityLevel,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_crop_observation(
    document: dict,
    language: PersistenceLanguage = PersistenceLanguage.USER_LANGUAGE,
) -> CropObservation:
    ai_diag_raw = document.get("ai_diagnosis")
    ai_diagnosis_result = None
    if ai_diag_raw:
        if (
            language.value in ai_diag_raw
            or PersistenceLanguage.ENGLISH.value in ai_diag_raw
        ):
            translatable = (
                ai_diag_raw.get(language.value)
                or ai_diag_raw.get(PersistenceLanguage.ENGLISH.value)
                or {}
            )
            invariant_data = {
                "issue_type": ai_diag_raw.get("issue_type", IssueType.OTHER),
                "confidence_score": ai_diag_raw.get("confidence_score", 0.0),
                "severity": ai_diag_raw.get("severity", SeverityLevel.MEDIUM),
            }
            ai_diagnosis_result = CropDiagnosisResult.model_validate(
                {
                    **invariant_data,
                    **translatable,
                }
            )
        else:
            ai_diagnosis_result = CropDiagnosisResult.model_validate(ai_diag_raw)

    obs_data = dict(document)
    obs_data["ai_diagnosis"] = ai_diagnosis_result
    return CropObservation.model_validate(obs_data)


async def create(
    observation: CropObservation,
) -> CropObservation:
    await get_crop_observations_collection().insert_one(
        observation.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return observation


async def get_by_id(
    observation_id: str,
    crop_id: Optional[str] = None,
    language: PersistenceLanguage = PersistenceLanguage.USER_LANGUAGE,
) -> Optional[CropObservation]:
    query = {"_id": observation_id}
    if crop_id:
        query["crop_id"] = crop_id
    doc = await get_crop_observations_collection().find_one(query)
    if not doc:
        return None
    return _to_crop_observation(doc, language=language)


async def list_by_crop(
    crop_id: str,
    limit: int = 100,
    language: PersistenceLanguage = PersistenceLanguage.USER_LANGUAGE,
) -> List[CropObservation]:
    cursor = (
        get_crop_observations_collection()
        .find({"crop_id": crop_id})
        .sort("observation_date", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_to_crop_observation(doc, language=language) for doc in docs]


async def save(
    observation: CropObservation,
) -> CropObservation:
    await get_crop_observations_collection().replace_one(
        {"_id": observation.id},
        observation.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return observation


async def save_diagnosis(
    observation_id: str,
    crop_id: str,
    diagnosis_doc: CropDiagnosisDocument,
    recommendation_id: Optional[str] = None,
) -> None:
    update_data = {
        "ai_diagnosis": diagnosis_doc.model_dump(exclude_none=True, mode="json"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if recommendation_id:
        update_data["agricultural_input_recommendation_id"] = recommendation_id

    await get_crop_observations_collection().update_one(
        {"_id": observation_id, "crop_id": crop_id},
        {"$set": update_data},
    )


async def delete(observation_id: str, crop_id: Optional[str] = None) -> bool:
    query = {"_id": observation_id}
    if crop_id:
        query["crop_id"] = crop_id
    result = await get_crop_observations_collection().delete_one(query)
    return result.deleted_count > 0
