from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from sqlalchemy import select

from config.dependencies import get_current_user, get_s3_storage_client
from database import (
    get_db,
    UserProfileModel,
    UserModel
)

from schemas.profiles import ProfileResponseSchema
from storages import S3StorageInterface
from validation import (
    validate_name,
    validate_gender,
    validate_birth_date,
    validate_image,
)


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

    is_admin = current_user.group.name in ("admin", "moderator")
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    user = await db.get(UserModel, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    # if existing.scalars().first():
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="User already has a profile."
    #     )


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
    profile = UserProfileModel(
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
