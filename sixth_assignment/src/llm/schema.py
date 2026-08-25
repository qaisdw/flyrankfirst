from pydantic import BaseModel, Field
from enum import Enum

class CategoryEnum(str, Enum):
    billing = "billing"
    bug = "bug"
    feature = "feature"
    other = "other"

class UrgencyEnum(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"

class TriageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="The incoming support message")

class TriageResponse(BaseModel):
    category: CategoryEnum
    urgency: UrgencyEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., max_length=200)