from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class WidgetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    widget_type: str = "signup"
    button_text: str = "Submit"

class WidgetResponse(BaseModel):
    id: str
    owner_id: str
    title: str
    widget_type: str
    button_text: str
    created_at: datetime
    embed_snippet: Optional[str] = None

    class Config:
        from_attributes = True

class SubmissionCreate(BaseModel):
    widget_id: str
    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=100)
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    hp_field: Optional[str] = Field(default=None) # Honeypot field for spam detection

class SubmissionResponse(BaseModel):
    id: str
    widget_id: str
    payload: Dict[str, Any]
    ip_address: Optional[str]
    geo_country: Optional[str]
    geo_city: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True