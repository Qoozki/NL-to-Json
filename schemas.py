"""Pydantic models: allowed values, the API request body, and the intermediate shapes."""
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# Allowed values

class AllowedCategory(str, Enum):
    ELECTRONICS = "ELECTRONICS"
    APPAREL = "APPAREL"
    HOME_GOODS = "HOME_GOODS"


class AllowedStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BACKORDERED = "BACKORDERED"
    DISCONTINUED = "DISCONTINUED"


class SortField(str, Enum):
    PRICE = "price"
    NAME = "name"


# GT/LT are strict (<, >), GTE/LTE are inclusive (<=, >=), BETWEEN is inclusive on both ends.
PriceOperator = Literal["EQUALS", "GT", "GTE", "LT", "LTE", "BETWEEN"]


# The request we send to the product API

class CategoryFilter(BaseModel):
    field: Literal["category"] = "category"
    operator: Literal["EQUALS", "IN"]
    value: Union[AllowedCategory, List[AllowedCategory]]


class StatusFilter(BaseModel):
    field: Literal["status"] = "status"
    operator: Literal["EQUALS", "IN"]
    value: Union[AllowedStatus, List[AllowedStatus]]


Price = Annotated[float, Field(ge=0)]


class PriceFilter(BaseModel):
    field: Literal["price"] = "price"
    operator: PriceOperator
    value: Union[Price, List[Price]]

    @model_validator(mode="after")
    def _check_shape(self):
        if self.operator == "BETWEEN":
            if not (isinstance(self.value, list) and len(self.value) == 2 and self.value[0] <= self.value[1]):
                raise ValueError("BETWEEN needs [min, max] with min <= max")
        elif isinstance(self.value, list):
            raise ValueError(f"{self.operator} needs a single number")
        return self


class SortItem(BaseModel):
    field: SortField
    direction: Literal["ASC", "DESC"]


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class APIRequestBody(BaseModel):
    filters: List[Union[CategoryFilter, StatusFilter, PriceFilter]]
    sort: Optional[List[SortItem]] = None
    pagination: Pagination


# Intermediate shapes

class Labels(BaseModel):
    """Step 1 (LLM) output: verbatim phrases from the query, one per slot."""
    status: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    sort: Optional[str] = None
    pagination: Optional[str] = None
    unsupported: Optional[str] = None   # conditions that fit none of the slots above


class PriceCondition(BaseModel):
    operator: PriceOperator
    value: Union[float, List[float]]


class Canonical(BaseModel):
    """Normalised values, produced deterministically from the query + labels."""
    status: List[AllowedStatus] = []
    category: List[AllowedCategory] = []
    prices: List[PriceCondition] = []
    sort: List[SortItem] = []
    limit: Optional[int] = None
    page: Optional[int] = None
