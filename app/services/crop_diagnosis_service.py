import asyncio
import json
import logging
from typing import Optional

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from app.ai.prompts.prompt_manager import PromptManager
from app.core.config import settings
from app.core.errors import (
    CultivationCropNotFound,
    DependencyUnavailable,
    ErrorCode,
    InternalOperationFailed,
    NotFoundError,
)
from app.infrastructure.providers.gemini import is_gemini_dependency_error
from app.repositories import crop_observation_repository
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendationDocument,
    AgriculturalInputRecommendationTranslatableFields,
)
from app.schemas.crop_observation import (
    CropDiagnosisDocument,
    CropDiagnosisResult,
    CropDiagnosisTranslatableFields,
    CropObservation,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import (
    agricultural_input_service,
    cultivation_crop_service,
    storage_service,
    translation_service,
)

logger = logging.getLogger(__name__)


class DiagnosisAndRemedyOutput(BaseModel):
    diagnosis: CropDiagnosisResult
    recommendation: Optional[AgriculturalInputRecommendationTranslatableFields] = None


def _call_vision_diagnosis_sync(
    *,
    prompt: str,
    image_parts: list[genai_types.Part],
) -> str:
    contents = [*image_parts, prompt] if image_parts else [prompt]
    with genai.Client() as client:
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return response.text or ""


async def diagnose_crop_observation(
    *,
    crop_id: str,
    observation_id: str,
    user_id: str,
) -> CropObservation:
    """
    Executes multimodal Gemini vision diagnosis on observation field photos and notes.
    Saves the diagnosis and, if an issue is detected, persists structured agricultural
    input recommendations with Organic and Chemical treatment strategies.
    """
    observation = await crop_observation_repository.get_by_id(
        observation_id=observation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )
    if not observation or observation.user_id != user_id:
        raise NotFoundError("Crop observation not found.")

    crop = await cultivation_crop_service.get_cultivation_crop_by_crop_id(
        crop_id=crop_id,
        user_id=user_id,
        language=PersistenceLanguage.ENGLISH,
    )
    if not crop:
        raise CultivationCropNotFound(crop_id)

    # Download image bytes (up to 4)
    image_parts: list[genai_types.Part] = []
    for file_id in observation.image_file_ids[:4]:
        try:
            file_meta, data_bytes = await storage_service.download_file(
                file_id=file_id,
                user_id=user_id,
            )
            image_parts.append(
                genai_types.Part.from_bytes(
                    data=data_bytes,
                    mime_type=file_meta.content_type or "image/jpeg",
                )
            )
        except Exception as exc:
            logger.warning("Failed to download observation image %s: %s", file_id, exc)

    crop_display_name = f"{crop.name} ({crop.variety})" if crop.variety else crop.name
    prompt = PromptManager.get_prompt(
        "pest_disease_diagnosis",
        crop_name=crop_display_name,
        growth_stage=observation.growth_stage or "",
        observation_date=str(observation.observation_date),
        notes=observation.notes or "",
        audio_transcription=observation.audio_transcription or "",
        diagnosis_schema_json=json.dumps(
            DiagnosisAndRemedyOutput.model_json_schema(), indent=2
        ),
    )

    try:
        raw_response = await asyncio.to_thread(
            _call_vision_diagnosis_sync,
            prompt=prompt,
            image_parts=image_parts,
        )
        parsed = DiagnosisAndRemedyOutput.model_validate_json(raw_response)
    except Exception as exc:
        if is_gemini_dependency_error(exc):
            raise DependencyUnavailable(
                "AI diagnosis service is temporarily unavailable.",
                code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
            ) from exc
        logger.error("Failed to parse diagnosis output: %s", exc)
        raise InternalOperationFailed(
            "Failed to process crop health diagnosis."
        ) from exc

    # Separate invariant and translatable diagnosis fields
    diag_english = CropDiagnosisTranslatableFields(
        issue_name=parsed.diagnosis.issue_name,
        symptoms=parsed.diagnosis.symptoms,
        affected_parts=parsed.diagnosis.affected_parts,
        diagnosis_summary=parsed.diagnosis.diagnosis_summary,
    )

    try:
        diag_user_lang = await translation_service.to_user_language(
            user_id=user_id,
            fields=diag_english,
        )
    except Exception as exc:
        logger.warning("Failed to translate crop diagnosis to user language: %s", exc)
        diag_user_lang = diag_english

    diagnosis_doc = CropDiagnosisDocument(
        issue_type=parsed.diagnosis.issue_type,
        confidence_score=parsed.diagnosis.confidence_score,
        severity=parsed.diagnosis.severity,
        english=diag_english,
        user_language=diag_user_lang,
    )

    rec_id: Optional[str] = None
    if parsed.recommendation and parsed.recommendation.strategies:
        rec_english = parsed.recommendation
        try:
            rec_user_lang = await translation_service.to_user_language(
                user_id=user_id,
                fields=rec_english,
            )
        except Exception as exc:
            logger.warning("Failed to translate recommendation: %s", exc)
            rec_user_lang = rec_english

        rec_doc = AgriculturalInputRecommendationDocument(
            cultivation_crop_id=crop_id,
            english=rec_english,
            user_language=rec_user_lang,
        )
        rec_doc = (
            await agricultural_input_service._create_agricultural_input_recommendation(
                rec_doc
            )
        )
        rec_id = rec_doc.id

    await crop_observation_repository.save_diagnosis(
        observation_id=observation_id,
        crop_id=crop_id,
        diagnosis_doc=diagnosis_doc,
        recommendation_id=rec_id,
    )

    updated_observation = await crop_observation_repository.get_by_id(
        observation_id=observation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    return updated_observation or observation
