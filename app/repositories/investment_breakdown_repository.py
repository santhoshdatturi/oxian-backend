from datetime import datetime, timezone

from app.infrastructure.database.collections import get_investment_breakdowns_collection
from app.schemas.cultivation_task import InvestmentActualCostInput
from app.schemas.generic_types import MoneyValue, PersistenceLanguage
from app.schemas.investment_breakdown import (
    InvestmentBreakdown,
    InvestmentBreakdownDocument,
    InvestmentBreakdownInvariantFields,
    InvestmentBreakdownTranslatableFields,
    InvestmentItem,
)


def _to_investment_breakdown(
    document: dict,
    language: PersistenceLanguage,
) -> InvestmentBreakdown:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in InvestmentBreakdownInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = InvestmentBreakdownInvariantFields.model_validate(invariant_data)
    return InvestmentBreakdown.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


def _touch(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    return breakdown.model_copy(update={"updated_at": datetime.now(timezone.utc)})


async def create(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    breakdown = _touch(breakdown)
    await get_investment_breakdowns_collection().insert_one(
        breakdown.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return breakdown


async def save(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    existing = await get_investment_breakdowns_collection().find_one(
        {"_id": breakdown.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        breakdown = breakdown.model_copy(update={"created_at": existing["created_at"]})
    breakdown = _touch(breakdown)
    await get_investment_breakdowns_collection().replace_one(
        {"_id": breakdown.id},
        breakdown.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return breakdown


async def save_language(
    breakdown: InvestmentBreakdown,
    language: PersistenceLanguage,
) -> InvestmentBreakdown:
    breakdown = breakdown.model_copy(update={"updated_at": datetime.now(timezone.utc)})
    translatable_fields = InvestmentBreakdownTranslatableFields.model_validate(
        breakdown
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = InvestmentBreakdownInvariantFields.model_validate(
        breakdown
    ).model_dump(exclude_none=True, mode="json")
    await get_investment_breakdowns_collection().update_one(
        {"_id": breakdown.id, "crop_id": breakdown.crop_id},
        {
            "$set": {
                **invariant_fields,
                "updated_at": breakdown.updated_at,
                language.value: translatable_fields,
            },
            "$setOnInsert": {"created_at": breakdown.created_at},
        },
        upsert=True,
    )
    return breakdown


async def get_by_crop_id(
    crop_id: str,
    language: PersistenceLanguage,
) -> InvestmentBreakdown | None:
    projection = {
        "_id": 1,
        "crop_id": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    document = await get_investment_breakdowns_collection().find_one(
        {"crop_id": crop_id}, projection
    )
    if not document:
        return None
    return _to_investment_breakdown(document, language)


async def get_document_by_crop_id(
    crop_id: str,
) -> InvestmentBreakdownDocument | None:
    document = await get_investment_breakdowns_collection().find_one(
        {"crop_id": crop_id}
    )
    if not document:
        return None
    return InvestmentBreakdownDocument.model_validate(document)


async def get_crop_id_by_id(breakdown_id: str) -> str | None:
    document = await get_investment_breakdowns_collection().find_one(
        {"_id": breakdown_id},
        {"crop_id": 1},
    )
    if not document:
        return None
    return document.get("crop_id")


async def delete(breakdown_id: str, crop_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": breakdown_id}
    if crop_id:
        query["crop_id"] = crop_id
    result = await get_investment_breakdowns_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_crop(crop_id: str) -> int:
    result = await get_investment_breakdowns_collection().delete_many(
        {"crop_id": crop_id}
    )
    return result.deleted_count


async def record_actual_costs(
    crop_id: str,
    actual_costs: list[InvestmentActualCostInput],
) -> InvestmentBreakdownDocument | None:
    if not actual_costs:
        return await get_document_by_crop_id(crop_id)

    doc = await get_document_by_crop_id(crop_id)
    if not doc:
        return None

    currency = doc.english.profitability.estimated_total_cost.currency

    def _find_item(
        items: list[InvestmentItem], cost: InvestmentActualCostInput
    ) -> InvestmentItem | None:
        cost_reason = cost.reason.strip().lower()
        for it in items:
            it_reason = it.reason.strip().lower()
            if (
                cost_reason == it_reason
                or cost_reason in it_reason
                or it_reason in cost_reason
            ):
                return it
        for it in items:
            if it.category == cost.category and it.actual_cost is None:
                return it
        return None

    for cost_input in actual_costs:
        # Update canonical english
        target_en = _find_item(doc.english.investments, cost_input)
        if target_en:
            target_en.actual_cost = cost_input.actual_cost
        else:
            doc.english.investments.append(
                InvestmentItem(
                    category=cost_input.category,
                    reason=cost_input.reason,
                    estimated_cost=cost_input.actual_cost,
                    actual_cost=cost_input.actual_cost,
                )
            )
            # Add to estimated total cost to keep model validation consistent
            doc.english.profitability.estimated_total_cost.amount += (
                cost_input.actual_cost.amount
            )
            doc.english.profitability.estimated_net_profit.amount = (
                doc.english.profitability.estimated_gross_income.amount
                - doc.english.profitability.estimated_total_cost.amount
            )

        # Update user language
        target_user = _find_item(doc.user_language.investments, cost_input)
        if target_user:
            target_user.actual_cost = cost_input.actual_cost
        else:
            doc.user_language.investments.append(
                InvestmentItem(
                    category=cost_input.category,
                    reason=cost_input.reason,
                    estimated_cost=cost_input.actual_cost,
                    actual_cost=cost_input.actual_cost,
                )
            )
            doc.user_language.profitability.estimated_total_cost.amount += (
                cost_input.actual_cost.amount
            )
            doc.user_language.profitability.estimated_net_profit.amount = (
                doc.user_language.profitability.estimated_gross_income.amount
                - doc.user_language.profitability.estimated_total_cost.amount
            )

    # Recompute total actual cost
    total_spent = sum(
        item.actual_cost.amount
        for item in doc.english.investments
        if item.actual_cost is not None
    )
    actual_cost_money = MoneyValue(amount=total_spent, currency=currency)
    doc.english.profitability.actual_total_cost = actual_cost_money
    doc.user_language.profitability.actual_total_cost = actual_cost_money

    # Recompute actual net profit
    gross_income = doc.english.profitability.estimated_gross_income.amount
    actual_profit = gross_income - total_spent
    doc.english.profitability.actual_net_profit = MoneyValue(
        amount=actual_profit, currency=currency
    )
    doc.user_language.profitability.actual_net_profit = MoneyValue(
        amount=actual_profit, currency=currency
    )

    doc.updated_at = datetime.now(timezone.utc)
    await save(doc)
    return doc
