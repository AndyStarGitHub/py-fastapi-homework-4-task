from datetime import date
from pydantic import BaseModel, Field, field_validator
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateSchema(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    gender: str
    date_of_birth: date
    info: str
    avatar: bytes  # Очікується multipart/form-data (image)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v):
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def validate_gender_value(cls, v):
        return validate_gender(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date):
        return validate_birth_date(v)

    @field_validator("info")
    @classmethod
    def validate_info_not_empty(cls, v: str):
        if not v.strip():
            raise ValueError("Info cannot be empty or only whitespace.")
        return v

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v: bytes):
        return validate_image(v)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar_url: str

    model_config = {"from_attributes": True}
