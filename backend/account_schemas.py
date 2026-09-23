"""Account data is private; public profiles never include login credentials."""
from typing import Annotated, Literal
import re

from pydantic import Field, StringConstraints, TypeAdapter, HttpUrl, field_validator

from .schemas import ApiModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value):
            raise ValueError('Укажите корректный email')
        return value


class RegisterRequest(LoginRequest):
    password: Password
    name: Name
    role: Literal['business', 'team']
    profile_name: Name


class UserPatch(ApiModel):
    name: Name


class PasswordChange(ApiModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class ProfileFields(ApiModel):
    name: Name = 'Профиль'
    description: str = Field(default='', max_length=3000)
    industry: str = Field(default='', max_length=120)
    website: str = Field(default='', max_length=2000)
    contact: str = Field(default='', max_length=500)
    interests: list[Tag] = Field(default_factory=list, max_length=30)
    skills: list[Tag] = Field(default_factory=list, max_length=30)
    technologies: list[Tag] = Field(default_factory=list, max_length=30)
    portfolio_urls: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('website')
    @classmethod
    def validate_website(cls, value: str) -> str:
        value = value.strip()
        if value:
            TypeAdapter(HttpUrl).validate_python(value)
        return value

    @field_validator('portfolio_urls')
    @classmethod
    def validate_portfolio(cls, values: list[str]) -> list[str]:
        for value in values:
            TypeAdapter(HttpUrl).validate_python(value)
        return [value.strip() for value in values]


class ProfilePatch(ProfileFields):
    pass


class ProfileMember(ApiModel):
    name: str
    role: Literal['owner']


class PublicProfile(ProfileFields):
    id: str
    role: Literal['business', 'team']
    team_id: str | None
    members: list[ProfileMember]
    team_points: int = Field(ge=0)


class AccountResponse(ApiModel):
    id: str
    email: str
    name: str
    profile: PublicProfile


class SessionResponse(ApiModel):
    user: AccountResponse
    csrf_token: str
    expires_at: int
