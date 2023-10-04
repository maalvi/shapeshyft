import uuid
from datetime import datetime, timedelta

import pytz
from tortoise import fields, models

from app.config import AUTH
from app.schemas.auth import TokenResponse
from app.services.auth import create_access_token, hash_password
from app.utils.exception import ShapeShyftException
from app.utils.validation import is_valid_email, is_valid_phone_number

from .audit import AuditableModel
from .token import UserToken


class UserAccount(AuditableModel):
    uuid = fields.UUIDField(pk=True, default=uuid.uuid4)
    phone_number = fields.CharField(max_length=30, unique=True)
    email = fields.CharField(max_length=150, null=True, unique=True)

    first_name = fields.CharField(max_length=100, null=True)
    last_name = fields.CharField(max_length=110, null=True)

    date_joined = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(auto_now=True)

    hashed_password = fields.CharField(max_length=300, null=True)

    class Meta:
        table = "user_account"

    def __str__(self):
        return f"{self.phone_number}"

    async def set_password(self, password: str, save=True) -> None:
        self.hashed_password = await hash_password(password)
        if save:
            await self.save()

    async def check_password(self, password) -> bool:
        return await check_password(self.hashed_password, password)

    async def create_access_token(self) -> TokenResponse:
        jti = uuid.uuid4()
        refresh_expire = datetime.utcnow() + timedelta(
            days=AUTH["REFRESH_TOKEN_EXPIRE_DAYS"]
        )

        token: TokenResponse = await create_access_token(
            self.uuid,
            jti,
            self.phone_number,
            self.email,
            self.type,
        )
        await UserToken.create(
            jti=jti,
            user=self,
            refresh_token=token.refresh_token,
            expire=refresh_expire,
        )
        return token

    @classmethod
    async def get_by_identifier(cls, identifier: str) -> "UserAccount":
        if is_valid_phone_number(identifier):
            user_field = "phone_number"
        elif is_valid_email(identifier):
            user_field = "email"
        else:
            raise ValueError(
                "Invalid identifier. Must be an email or phone number in E.164 format"
            )

        query = {user_field: identifier.lower()}

        user = await cls.get_or_none(**query)

        if not user:
            raise ShapeShyftException("E1002")

        return user
