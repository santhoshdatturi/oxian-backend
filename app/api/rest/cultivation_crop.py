from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user_id
from app.core.errors import (
    AgriculturalInputNotFound,
    CultivationCropNotFound,
    CultivationTaskNotFound,
    IntercroppingCultivationNotFound,
    InvestmentBreakdownNotFound,
)
from app.schemas.agricultural_input_plan import AgriculturalInputPlan
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendation,
)
from app.schemas.cultivation_crop import (
    CultivationCrop,
    CultivationCropInput,
    IntercroppingCultivation,
    IntercroppingCultivationInput,
)
from app.schemas.cultivation_task import (
    CompleteTaskRequest,
    CreateCultivationTaskInput,
    CultivationTask,
    SkipTaskRequest,
    TaskState,
)
from app.schemas.investment_breakdown import InvestmentBreakdown
from app.services import (
    agricultural_input_service,
    cultivation_crop_service,
    cultivation_task_service,
    investment_breakdown_service,
)
from app.services.crop_planning_service import (
    CropPlan,
    generate_crop_plan,
    plan_next_stage,
)

router = APIRouter(prefix="/cultivation-crops", tags=["Cultivation Crops"])


@router.get("/farms/{farm_id}", response_model=list[CultivationCrop])
async def list_cultivation_crops(
    farm_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationCrop]:
    return await cultivation_crop_service.list_cultivation_crops(
        user_id=user_id,
        farm_id=farm_id,
        limit=limit,
    )


@router.post(
    "/farms/{farm_id}",
    response_model=CultivationCrop,
    status_code=201,
)
async def create_cultivation_crop(
    farm_id: str,
    input: CultivationCropInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    return await cultivation_crop_service.create_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        input=input,
    )


@router.get(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def get_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return crop


@router.put(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def update_cultivation_crop(
    farm_id: str,
    crop_id: str,
    input: CultivationCropInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    return await cultivation_crop_service.update_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
        input=input,
    )


@router.delete("/farms/{farm_id}/{crop_id}", status_code=204)
async def delete_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await cultivation_crop_service.delete_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )
    if not deleted:
        raise CultivationCropNotFound(crop_id)
    return


@router.post(
    "/farms/{farm_id}/intercropping",
    response_model=IntercroppingCultivation,
    status_code=201,
)
async def create_intercropping_cultivation(
    farm_id: str,
    input: IntercroppingCultivationInput,
    user_id: str = Depends(get_current_user_id),
) -> IntercroppingCultivation:
    return await cultivation_crop_service.create_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        input=input,
    )


@router.put(
    "/farms/{farm_id}/intercropping/{intercropping_id}",
    response_model=IntercroppingCultivation,
)
async def update_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    input: IntercroppingCultivationInput,
    user_id: str = Depends(get_current_user_id),
) -> IntercroppingCultivation:
    return await cultivation_crop_service.update_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        intercropping_id=intercropping_id,
        input=input,
    )


@router.delete("/farms/{farm_id}/intercropping/{intercropping_id}", status_code=204)
async def delete_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await cultivation_crop_service.delete_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        intercropping_id=intercropping_id,
    )
    if not deleted:
        raise IntercroppingCultivationNotFound(intercropping_id)
    return


@router.post(
    "/farms/{farm_id}/{crop_id}/plan",
    response_model=CropPlan,
    status_code=202,
)
async def create_crop_plan(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropPlan:
    return await generate_crop_plan(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )


@router.post(
    "/farms/{farm_id}/{crop_id}/plan-next-stage",
    response_model=CropPlan,
    status_code=202,
)
async def create_crop_plan_next_stage_for_farm(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropPlan:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await plan_next_stage(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )


@router.post(
    "/{crop_id}/plan-next-stage",
    response_model=CropPlan,
    status_code=202,
)
async def create_crop_plan_next_stage(
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropPlan:
    crop = await cultivation_crop_service.get_cultivation_crop_by_crop_id(
        user_id=user_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await plan_next_stage(
        user_id=user_id,
        farm_id=crop.farm_id,
        crop_id=crop_id,
    )


# --- Cultivation Tasks Query Endpoints ---


@router.get(
    "/farms/{farm_id}/{crop_id}/tasks",
    response_model=list[CultivationTask],
)
async def list_cultivation_tasks_for_farm(
    farm_id: str,
    crop_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationTask]:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await cultivation_task_service.list_cultivation_tasks(
        crop_id=crop_id, user_id=user_id, limit=limit
    )


@router.get(
    "/{crop_id}/tasks",
    response_model=list[CultivationTask],
)
async def list_cultivation_tasks(
    crop_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationTask]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)
    return await cultivation_task_service.list_cultivation_tasks(
        crop_id=crop_id, user_id=user_id, limit=limit
    )


@router.get(
    "/farms/{farm_id}/{crop_id}/tasks/{task_id}",
    response_model=CultivationTask,
)
async def get_cultivation_task_for_farm(
    farm_id: str,
    crop_id: str,
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    task = await cultivation_task_service.get_cultivation_task(
        task_id=task_id, user_id=user_id
    )
    if task is None or task.crop_id != crop_id:
        raise CultivationTaskNotFound(task_id)
    return task


@router.get(
    "/{crop_id}/tasks/{task_id}",
    response_model=CultivationTask,
)
async def get_cultivation_task(
    crop_id: str,
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)
    task = await cultivation_task_service.get_cultivation_task(
        task_id=task_id, user_id=user_id
    )
    if task is None or task.crop_id != crop_id:
        raise CultivationTaskNotFound(task_id)
    return task


@router.post(
    "/farms/{farm_id}/{crop_id}/tasks",
    response_model=CultivationTask,
    status_code=201,
)
async def create_custom_task_for_farm(
    farm_id: str,
    crop_id: str,
    input: CreateCultivationTaskInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await cultivation_task_service.add_custom_task(
        crop_id=crop_id,
        user_id=user_id,
        task_input=input,
    )


@router.post(
    "/{crop_id}/tasks",
    response_model=CultivationTask,
    status_code=201,
)
async def create_custom_task(
    crop_id: str,
    input: CreateCultivationTaskInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    return await cultivation_task_service.add_custom_task(
        crop_id=crop_id,
        user_id=user_id,
        task_input=input,
    )


@router.patch(
    "/farms/{farm_id}/{crop_id}/tasks/{task_id}/complete",
    response_model=CultivationTask,
)
async def complete_cultivation_task_for_farm(
    farm_id: str,
    crop_id: str,
    task_id: str,
    payload: CompleteTaskRequest = CompleteTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await cultivation_task_service.complete_cultivation_task(
        task_id=task_id,
        crop_id=crop_id,
        user_id=user_id,
        execution_notes=payload.execution_notes,
        actual_costs=payload.actual_costs,
        completed_at=payload.completed_at,
    )


@router.patch(
    "/{crop_id}/tasks/{task_id}/complete",
    response_model=CultivationTask,
)
async def complete_cultivation_task(
    crop_id: str,
    task_id: str,
    payload: CompleteTaskRequest = CompleteTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    return await cultivation_task_service.complete_cultivation_task(
        task_id=task_id,
        crop_id=crop_id,
        user_id=user_id,
        execution_notes=payload.execution_notes,
        actual_costs=payload.actual_costs,
        completed_at=payload.completed_at,
    )


@router.post(
    "/farms/{farm_id}/{crop_id}/tasks/{task_id}/skip",
    response_model=CultivationTask,
)
async def skip_cultivation_task_for_farm(
    farm_id: str,
    crop_id: str,
    task_id: str,
    payload: SkipTaskRequest = SkipTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await cultivation_task_service.skip_cultivation_task(
        task_id=task_id,
        crop_id=crop_id,
        user_id=user_id,
        reason=payload.reason,
    )


@router.post(
    "/{crop_id}/tasks/{task_id}/skip",
    response_model=CultivationTask,
)
async def skip_cultivation_task(
    crop_id: str,
    task_id: str,
    payload: SkipTaskRequest = SkipTaskRequest(),
    user_id: str = Depends(get_current_user_id),
) -> CultivationTask:
    return await cultivation_task_service.skip_cultivation_task(
        task_id=task_id,
        crop_id=crop_id,
        user_id=user_id,
        reason=payload.reason,
    )


@router.get(
    "/farms/{farm_id}/calendar/tasks",
    response_model=list[CultivationTask],
)
async def list_farm_calendar_tasks_crop_alias(
    farm_id: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    status: Optional[TaskState] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationTask]:
    return await cultivation_task_service.list_farm_calendar_tasks(
        farm_id=farm_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )


# --- Investment Breakdown Query Endpoints ---


@router.get(
    "/farms/{farm_id}/{crop_id}/investment-breakdown",
    response_model=InvestmentBreakdown,
)
async def get_investment_breakdown_for_farm(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> InvestmentBreakdown:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    breakdown = await investment_breakdown_service.get_investment_breakdown_by_crop(
        crop_id=crop_id, user_id=user_id
    )
    if breakdown is None:
        raise InvestmentBreakdownNotFound(crop_id)
    return breakdown


@router.get(
    "/{crop_id}/investment-breakdown",
    response_model=InvestmentBreakdown,
)
async def get_investment_breakdown(
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> InvestmentBreakdown:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)
    breakdown = await investment_breakdown_service.get_investment_breakdown_by_crop(
        crop_id=crop_id, user_id=user_id
    )
    if breakdown is None:
        raise InvestmentBreakdownNotFound(crop_id)
    return breakdown


# --- Agricultural Input Recommendations Query Endpoints ---


@router.get(
    "/farms/{farm_id}/{crop_id}/agricultural-inputs",
    response_model=list[AgriculturalInputRecommendation],
)
async def list_agricultural_inputs_for_farm(
    farm_id: str,
    crop_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[AgriculturalInputRecommendation]:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await agricultural_input_service.list_agricultural_input_recommendations(
        crop_id=crop_id, user_id=user_id, limit=limit
    )


@router.get(
    "/farms/{farm_id}/{crop_id}/agricultural-input-plans",
    response_model=list[AgriculturalInputPlan],
)
async def list_agricultural_input_plans_for_farm(
    farm_id: str,
    crop_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[AgriculturalInputPlan]:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return await agricultural_input_service.list_agricultural_input_plans(
        crop_id=crop_id, user_id=user_id, limit=limit
    )


@router.get(
    "/farms/{farm_id}/{crop_id}/agricultural-input-plans/{plan_id}",
    response_model=AgriculturalInputPlan,
)
async def get_agricultural_input_plan_for_farm(
    farm_id: str,
    crop_id: str,
    plan_id: str,
    user_id: str = Depends(get_current_user_id),
) -> AgriculturalInputPlan:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    plan = await agricultural_input_service.get_agricultural_input_plan(
        plan_id=plan_id, user_id=user_id
    )
    if plan is None:
        raise AgriculturalInputNotFound(plan_id)
    return plan


@router.get(
    "/{crop_id}/agricultural-inputs",
    response_model=list[AgriculturalInputRecommendation],
)
async def list_agricultural_inputs(
    crop_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[AgriculturalInputRecommendation]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)
    return await agricultural_input_service.list_agricultural_input_recommendations(
        crop_id=crop_id, user_id=user_id, limit=limit
    )


@router.get(
    "/farms/{farm_id}/{crop_id}/agricultural-inputs/{recommendation_id}",
    response_model=AgriculturalInputRecommendation,
)
async def get_agricultural_input_for_farm(
    farm_id: str,
    crop_id: str,
    recommendation_id: str,
    user_id: str = Depends(get_current_user_id),
) -> AgriculturalInputRecommendation:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id, farm_id=farm_id, crop_id=crop_id
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    input_rec = await agricultural_input_service.get_agricultural_input_recommendation(
        recommendation_id=recommendation_id, user_id=user_id
    )
    if input_rec is None or input_rec.cultivation_crop_id != crop_id:
        raise AgriculturalInputNotFound(recommendation_id)
    return input_rec


@router.get(
    "/{crop_id}/agricultural-inputs/{recommendation_id}",
    response_model=AgriculturalInputRecommendation,
)
async def get_agricultural_input(
    crop_id: str,
    recommendation_id: str,
    user_id: str = Depends(get_current_user_id),
) -> AgriculturalInputRecommendation:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise CultivationCropNotFound(crop_id)
    input_rec = await agricultural_input_service.get_agricultural_input_recommendation(
        recommendation_id=recommendation_id, user_id=user_id
    )
    if input_rec is None or input_rec.cultivation_crop_id != crop_id:
        raise AgriculturalInputNotFound(recommendation_id)
    return input_rec
