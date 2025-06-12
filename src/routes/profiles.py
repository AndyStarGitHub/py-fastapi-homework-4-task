from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import date

from database import get_db, UserModel, UserProfileModel
from dependencies import get_current_user
from schemas.profiles import ProfileResponseSchema
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)
from storage import S3StorageInterface, get_s3_storage_client  # ✅ тобі потрібно реалізувати ці інтерфейси

router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user profile",
    description="Creates a user profile for the specified user. Requires authentication."
)
async def create_user_profile(
    request: Request,
    user_id: int,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    gender: Annotated[str, Form()],
    date_of_birth: Annotated[str, Form()],
    info: Annotated[str, Form()],
    avatar: Annotated[UploadFile, File()],
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    # 1️⃣ Token validation already handled by Depends(get_current_user)
    # Add extra error if no auth header
    if not request.headers.get("authorization"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )

    if not request.headers["authorization"].startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    # 2️⃣ Authorization Rules
    is_admin = current_user.group.name in ("admin", "moderator")
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    # 3️⃣ User existence and status
    user = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    # 4️⃣ Check for existing profile
    existing = await db.execute(
        db.query(ProfileModel).filter(ProfileModel.user_id == user_id)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # ✅ Validation
    validated_first_name = validate_name(first_name)
    validated_last_name = validate_name(last_name)
    validated_gender = validate_gender(gender)
    validated_dob = validate_birth_date(date_of_birth)
    if not info.strip():
        raise HTTPException(status_code=400, detail="Info cannot be empty.")

    avatar_bytes = await avatar.read()
    validate_image(avatar_bytes)

    # 5️⃣ Upload to S3
    filename = f"{user_id}_avatar.jpg"  # or use UUID
    try:
        avatar_url = await s3_client.upload_file(file_data=avatar_bytes, filename=filename, folder="avatars")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    # 6️⃣ Create and store profile
    profile = ProfileModel(
        user_id=user_id,
        first_name=validated_first_name,
        last_name=validated_last_name,
        gender=validated_gender,
        date_of_birth=validated_dob,
        info=info.strip(),
        avatar_url=avatar_url
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponseSchema.model_validate(profile)
