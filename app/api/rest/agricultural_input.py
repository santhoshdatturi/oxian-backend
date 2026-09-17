from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user_id
from app.schemas.agricultural_input_plan import AgriculturalInputPlan
from app.schemas.cultivation_task import CultivationTask
from app.services import agricultural_input_service

router = APIRouter(tags=["Agricultural Inputs & Remedies"])


class SelectStrategyRequest(BaseModel):
    strategy_rank: int = Field(
        ..., ge=1, description="Rank of the selected treatment strategy (1 for Organic, 2 for Chemical, etc.)."
    )
    application_date: Optional[date] = Field(
        default=None, description="Date on which the farmer plans to execute the strategy."
    )
    notes: Optional[str] = Field(
        default=None, description="Execution notes or reminders."
    )


class SelectStrategyResponse(BaseModel):
    plan: AgriculturalInputPlan
    task: CultivationTask


@router.post(
    "/agricultural-inputs/{recommendation_id}/select-strategy",
    response_model=SelectStrategyResponse,
    status_code=201,
)
async def select_remedy_strategy(
    recommendation_id: str,
    payload: SelectStrategyRequest,
    user_id: str = Depends(get_current_user_id),
) -> SelectStrategyResponse:
    """
    Selects a treatment strategy from an agricultural input recommendation, commits it
    as an AgriculturalInputPlan, and automatically injects an actionable task into the
    cultivation calendar with investment tracking.
    """
    plan, task = await agricultural_input_service.select_remedy_strategy(
        recommendation_id=recommendation_id,
        strategy_rank=payload.strategy_rank,
        user_id=user_id,
        application_date=payload.application_date,
        notes=payload.notes,
    )
    return SelectStrategyResponse(plan=plan, task=task)


@router.get(
    "/cultivation-crops/{crop_id}/agricultural-input-plans",
    response_model=List[AgriculturalInputPlan],
)
async def list_agricultural_input_plans(
    crop_id: str,
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
) -> List[AgriculturalInputPlan]:
    """
    Lists the agricultural input treatment plans selected and committed for this crop.
    """
    return await agricultural_input_service.list_agricultural_input_plans(
        crop_id=crop_id,
        user_id=user_id,
        limit=limit,
    )
