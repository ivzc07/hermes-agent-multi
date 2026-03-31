from typing import Optional

from pydantic import Field

from webapi.models.common import WebAPIModel


class ProfileRecord(WebAPIModel):
    name: str
    path: str
    is_default: bool
    gateway_running: bool
    model: Optional[str] = None
    provider: Optional[str] = None
    has_env: bool = False
    skill_count: int = 0
    alias_path: Optional[str] = None


class ProfileListResponse(WebAPIModel):
    items: list[ProfileRecord]
    total: int


class ActiveProfileResponse(WebAPIModel):
    name: str


class ProfileCreateRequest(WebAPIModel):
    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    model: Optional[str] = None


class ProfileCreateResponse(WebAPIModel):
    name: str
    path: str


class ProfileSwitchRequest(WebAPIModel):
    name: str


class ProfileDeleteResponse(WebAPIModel):
    ok: bool
    name: str
    path: str
