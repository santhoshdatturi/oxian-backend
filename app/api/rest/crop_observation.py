from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user_id
from app.core.errors import CultivationCropNotFound, NotFoundError
from app.infrastructure.storage.enums import StorageEntity
from app.repositories import (
    crop_observation_repository,
    user_pref_repository,
)
from app.schemas.crop_observation import (
    CropObservation,
    CropObservationCreate,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import (
    crop_diagnosis_service,
    cultivation_crop_service,
    storage_service,
    transcription_service,
)

router = APIRouter(tags=["Crop Observations"])


@router.post(
    "/cultivation-crops/{crop_id}/observations",
    response_model=CropObservation,
    status_code=201,
)
async def create_crop_observation(
    crop_id: str,
    payload: CropObservationCreate,
    user_id: str = Depends(get_current_user_id),
) -> CropObservation:
    """
    Creates a new field observation with photos and/or voice notes.
    Automatically activates files in storage and transcribes voice notes.
    """
    crop = await cultivation_crop_service.get_cultivation_crop_by_crop_id(
        crop_id=crop_id,
        user_id=user_id,
    )
    if not crop:
        raise CultivationCropNotFound(crop_id)

    observation = CropObservation(
        crop_id=crop_id,
        farm_id=crop.farm_id,
        user_id=user_id,
        observation_date=payload.observation_date or date.today(),
        growth_stage=payload.growth_stage,
        image_file_ids=payload.image_file_ids,
        audio_file_id=payload.audio_file_id,
        notes=payload.notes,
    )

    # 1. Activate uploaded image files
    if payload.image_file_ids:
        try:
            await storage_service._activate_files(
                file_ids=payload.image_file_ids,
                entity=StorageEntity.OBSERVATION,
                entity_id=observation.id,
                user_id=user_id,
            )
        except Exception:
            pass

    # 2. Activate and transcribe voice note if present
    if payload.audio_file_id:
        try:
            await storage_service._activate_files(
                file_ids=[payload.audio_file_id],
                entity=StorageEntity.OBSERVATION,
                entity_id=observation.id,
                user_id=user_id,
            )
            file_meta, audio_bytes = await storage_service.download_file(
                file_id=payload.audio_file_id,
                user_id=user_id,
            )
            pref = await user_pref_repository.get_by_user_id(user_id)
            user_lang = pref.language_code if pref else None
            transcript = await transcription_service.transcribe_audio(
                audio_bytes=audio_bytes,
                mime_type=file_meta.content_type or "audio/mp4",
                user_language=user_lang,
            )
            if transcript:
                observation.audio_transcription = transcript
        except Exception:
            pass

    observation = await crop_observation_repository.create(observation)
    return observation


@router.get(
    "/cultivation-crops/{crop_id}/observations",
    response_model=List[CropObservation],
)
async def list_crop_observations(
    crop_id: str,
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
) -> List[CropObservation]:
    """
    Lists field observations recorded for a cultivation crop.
    """
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    return await crop_observation_repository.list_by_crop(
        crop_id=crop_id,
        limit=limit,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


@router.get(
    "/cultivation-crops/{crop_id}/observations/{observation_id}",
    response_model=CropObservation,
)
async def get_crop_observation(
    crop_id: str,
    observation_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropObservation:
    """
    Retrieves a single field observation by ID.
    """
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise NotFoundError("Crop observation not found.")

    observation = await crop_observation_repository.get_by_id(
        observation_id=observation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    if not observation or observation.user_id != user_id:
        raise NotFoundError("Crop observation not found.")
    return observation


@router.post(
    "/cultivation-crops/{crop_id}/observations/{observation_id}/diagnose",
    response_model=CropObservation,
)
async def diagnose_observation(
    crop_id: str,
    observation_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropObservation:
    """
    Triggers multimodal Gemini vision diagnosis on the photos and notes of an existing observation.
    """
    return await crop_diagnosis_service.diagnose_crop_observation(
        crop_id=crop_id,
        observation_id=observation_id,
        user_id=user_id,
    )
