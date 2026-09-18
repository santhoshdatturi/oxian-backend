from datetime import date
from typing import Optional

from app.core.errors import AgriculturalInputNotFound, ValidationFailed
from app.repositories import (
    agricultural_input_plan_repository,
    agricultural_input_recommendation_repository,
    investment_breakdown_repository,
)
from app.schemas.agricultural_input_plan import (
    AgriculturalInputPlan,
    AgriculturalInputPlanDocument,
    AgriculturalInputPlanTranslatableFields,
)
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendation,
    AgriculturalInputRecommendationDocument,
)
from app.schemas.cultivation_task import (
    CultivationTask,
    CultivationTaskDocument,
    CultivationTaskTranslatableFields,
    Investment,
    InvestmentCategory,
    Priority,
    TaskState,
)
from app.schemas.generic_types import Currency, MoneyValue, PersistenceLanguage
from app.schemas.investment_breakdown import InvestmentItem
from app.services import cultivation_crop_service, cultivation_task_service


async def list_agricultural_input_recommendations(
    *, crop_id: str, user_id: str, limit: int = 100
) -> list[AgriculturalInputRecommendation]:
    """Return accessible recommendations enriched with adopted plan details.

    Adopted plans whose original recommendation is unavailable are represented as
    synthetic recommendations. Returns an empty list when the user lacks crop access.
    """
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    recs = await agricultural_input_recommendation_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )
    plans = await agricultural_input_plan_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )
    existing_rec_ids = {r.id for r in recs}
    for plan in plans:
        matched = False
        for rec in recs:
            if rec.id == plan.recommendation_id:
                matched = True
                if rec.selected_strategy_rank is None:
                    rec.selected_strategy_rank = plan.selected_strategy.rank
                    rec.adopted_plan_id = plan.id
        if not matched and plan.id not in existing_rec_ids:
            synth_rec = AgriculturalInputRecommendation(
                id=plan.id,
                cultivation_crop_id=plan.cultivation_crop_id,
                title="Adopted Remedy Strategy",
                problem=plan.notes or "Scheduled treatment plan",
                strategies=[plan.selected_strategy],
                selected_strategy_rank=plan.selected_strategy.rank,
                adopted_plan_id=plan.id,
            )
            recs.append(synth_rec)
    return recs


async def get_agricultural_input_recommendation(
    *, recommendation_id: str, user_id: str
) -> AgriculturalInputRecommendation | None:
    crop_id = await agricultural_input_recommendation_repository.get_crop_id_by_id(
        recommendation_id
    )
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return None
    return await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def delete_agricultural_input_recommendation(
    *, recommendation_id: str, user_id: str
) -> bool:
    crop_id = await agricultural_input_recommendation_repository.get_crop_id_by_id(
        recommendation_id
    )
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return False
    return await agricultural_input_recommendation_repository.delete(
        recommendation_id=recommendation_id, crop_id=crop_id
    )


async def select_remedy_strategy(
    *,
    recommendation_id: str,
    strategy_rank: int,
    user_id: str,
    application_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> tuple[AgriculturalInputPlan, CultivationTask]:
    """Adopt a recommended strategy and return its localized plan and task.

    The application date defaults to today. The selection creates a plan and a
    pending calendar task, then attempts to update the crop's investment breakdown
    and recommendation adoption details without failing the selection if either
    supplementary update fails.

    Raises:
        AgriculturalInputNotFound: If the recommendation is inaccessible or missing,
            or the saved plan or task cannot be loaded.
        ValidationFailed: If ``strategy_rank`` does not identify a recommended
            strategy.
    """
    crop_id = await agricultural_input_recommendation_repository.get_crop_id_by_id(
        recommendation_id
    )
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        raise AgriculturalInputNotFound(recommendation_id)

    rec_user = await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    rec_eng = await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )
    if not rec_user or not rec_eng:
        raise AgriculturalInputNotFound(recommendation_id)

    strat_user = next((s for s in rec_user.strategies if s.rank == strategy_rank), None)
    strat_eng = next((s for s in rec_eng.strategies if s.rank == strategy_rank), None)
    if not strat_user or not strat_eng:
        raise ValidationFailed(
            f"Strategy with rank {strategy_rank} not found in recommendation."
        )

    app_date = application_date or date.today()

    # 1. Create and persist AgriculturalInputPlanDocument
    plan_doc = AgriculturalInputPlanDocument(
        cultivation_crop_id=crop_id,
        recommendation_id=recommendation_id,
        application_date=app_date,
        english=AgriculturalInputPlanTranslatableFields(
            selected_strategy=strat_eng,
            notes=notes,
        ),
        user_language=AgriculturalInputPlanTranslatableFields(
            selected_strategy=strat_user,
            notes=notes,
        ),
    )
    plan_doc = await agricultural_input_plan_repository.create(plan_doc)

    # 2. Automatically inject a CultivationTask into the calendar
    input_names_eng = ", ".join(inp.input_name for inp in strat_eng.inputs)
    input_names_user = ", ".join(inp.input_name for inp in strat_user.inputs)

    task_name_eng = (
        f"Apply {strat_eng.approach.capitalize()} Treatment: {input_names_eng}"
    )
    task_name_user = (
        f"Apply {strat_user.approach.capitalize()} Treatment: {input_names_user}"
    )

    steps_eng = "\n".join(
        f"{i+1}. {step}" for i, step in enumerate(strat_eng.application_steps)
    )
    steps_user = "\n".join(
        f"{i+1}. {step}" for i, step in enumerate(strat_user.application_steps)
    )

    task_doc = CultivationTaskDocument(
        crop_id=crop_id,
        planned_start_date=app_date,
        planned_end_date=app_date,
        status=TaskState.PENDING,
        priority=Priority.HIGH,
        skippable=False,
        english=CultivationTaskTranslatableFields(
            task_name=task_name_eng,
            description=f"{strat_eng.explanation}\n\nApplication Steps:\n{steps_eng}\n\nExpected Result: {strat_eng.expected_result}",
            agricultural_input_recommendation_id=recommendation_id,
            investments=[
                Investment(
                    category=InvestmentCategory.AGRICULTURAL_INPUT,
                    reason=task_name_eng,
                    estimated_cost=MoneyValue(amount=0.0, currency=Currency.INR),
                )
            ],
        ),
        user_language=CultivationTaskTranslatableFields(
            task_name=task_name_user,
            description=f"{strat_user.explanation}\n\nApplication Steps:\n{steps_user}\n\nExpected Result: {strat_user.expected_result}",
            agricultural_input_recommendation_id=recommendation_id,
            investments=[
                Investment(
                    category=InvestmentCategory.AGRICULTURAL_INPUT,
                    reason=task_name_user,
                    estimated_cost=MoneyValue(amount=0.0, currency=Currency.INR),
                )
            ],
        ),
    )
    task_doc = await cultivation_task_service._create_cultivation_task(task_doc)

    # 3. Add investment line item into InvestmentBreakdown
    try:
        breakdown = await investment_breakdown_repository.get_document_by_crop_id(
            crop_id
        )
        if breakdown:
            new_inv_eng = InvestmentItem(
                category=InvestmentCategory.AGRICULTURAL_INPUT,
                reason=task_name_eng,
                estimated_cost=MoneyValue(amount=0.0, currency=Currency.INR),
            )
            new_inv_user = InvestmentItem(
                category=InvestmentCategory.AGRICULTURAL_INPUT,
                reason=task_name_user,
                estimated_cost=MoneyValue(amount=0.0, currency=Currency.INR),
            )
            breakdown.english.investments.append(new_inv_eng)
            breakdown.user_language.investments.append(new_inv_user)
            await investment_breakdown_repository.save(breakdown)
    except Exception:
        pass

    # 4. Update AgriculturalInputRecommendationDocument with adoption details
    try:
        rec_doc = await agricultural_input_recommendation_repository.get_document_by_id(
            recommendation_id=recommendation_id, crop_id=crop_id
        )
        if rec_doc:
            rec_doc.selected_strategy_rank = strategy_rank
            rec_doc.adopted_plan_id = plan_doc.id
            rec_doc.adopted_task_id = task_doc.id
            await agricultural_input_recommendation_repository.save(rec_doc)
    except Exception:
        pass

    user_task = await cultivation_task_service.get_cultivation_task(
        task_id=task_doc.id,
        user_id=user_id,
    )
    user_plan = await agricultural_input_plan_repository.get_by_id(
        plan_id=plan_doc.id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    if user_plan is None or user_task is None:
        raise AgriculturalInputNotFound(plan_doc.id)
    return user_plan, user_task


async def list_agricultural_input_plans(
    *, crop_id: str, user_id: str, limit: int = 100
) -> list[AgriculturalInputPlan]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    return await agricultural_input_plan_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def _list_agricultural_input_recommendations(
    crop_id: str, limit: int = 100
) -> list[AgriculturalInputRecommendation]:
    return await agricultural_input_recommendation_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
        limit=limit,
    )


async def _get_agricultural_input_recommendation(
    recommendation_id: str, crop_id: str | None = None
) -> AgriculturalInputRecommendation | None:
    return await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_agricultural_input_recommendation(
    document: AgriculturalInputRecommendationDocument,
) -> AgriculturalInputRecommendationDocument:
    return await agricultural_input_recommendation_repository.create(document)

