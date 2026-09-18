from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator

from .agricultural_input_plan import (
    AgriculturalInputInvariantFields,
    AgriculturalInputStrategy,
    AgriculturalInputTranslatableFields,
)
from .generic_types import TranslatedFields


class AgriculturalInputRecommendationTranslatableFields(
    AgriculturalInputTranslatableFields
):
    """
    Fields for representing the core attributes of an agricultural input recommendation, which are translatable.
    """

    strategies: List[AgriculturalInputStrategy] = Field(
        min_length=1,
        description=("Alternative treatment strategies available to the farmer."),
    )

    @field_validator("strategies")
    @classmethod
    def unique_strategy_ranks(cls, v):
        ranks = [strategy.rank for strategy in v]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Strategy ranks must be unique")
        return v


class AgriculturalInputRecommendation(
    AgriculturalInputInvariantFields, AgriculturalInputRecommendationTranslatableFields
):
    """
    Represents an agricultural intervention recommendation
    generated for a crop issue, nutrient deficiency,
    growth stage, pest attack, disease, or management need.
    """

    selected_strategy_rank: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("selected_strategy_rank", "selectedStrategyRank"),
    )
    adopted_plan_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("adopted_plan_id", "adoptedPlanId"),
    )
    adopted_task_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("adopted_task_id", "adoptedTaskId"),
    )


TranslatedAgriculturalInputRecommendationFields = TranslatedFields[
    AgriculturalInputRecommendationTranslatableFields
]


class AgriculturalInputRecommendationDocument(
    AgriculturalInputInvariantFields, TranslatedAgriculturalInputRecommendationFields
):
    """
    MongoDB document model for storing agricultural input recommendations with both invariant and translatable fields.
    """

    selected_strategy_rank: Optional[int] = None
    adopted_plan_id: Optional[str] = None
    adopted_task_id: Optional[str] = None
