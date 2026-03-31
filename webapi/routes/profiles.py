import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException

from hermes_cli.profiles import (
    create_profile,
    delete_profile,
    get_active_profile,
    list_profiles,
    profile_exists,
    set_active_profile,
    validate_profile_name,
)
from webapi.models.profiles import (
    ActiveProfileResponse,
    ProfileCreateRequest,
    ProfileCreateResponse,
    ProfileDeleteResponse,
    ProfileListResponse,
    ProfileRecord,
    ProfileSwitchRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _profile_info_to_record(info) -> ProfileRecord:
    """Convert a ProfileInfo dataclass to a Pydantic ProfileRecord."""
    return ProfileRecord(
        name=info.name,
        path=str(info.path),
        is_default=info.is_default,
        gateway_running=info.gateway_running,
        model=info.model,
        provider=info.provider,
        has_env=info.has_env,
        skill_count=info.skill_count,
        alias_path=str(info.alias_path) if info.alias_path else None,
    )


@router.get("", response_model=ProfileListResponse)
async def api_list_profiles() -> ProfileListResponse:
    """List all profiles with their details."""
    loop = asyncio.get_running_loop()
    profiles = await loop.run_in_executor(None, list_profiles)
    items = [_profile_info_to_record(p) for p in profiles]
    return ProfileListResponse(items=items, total=len(items))


@router.get("/active", response_model=ActiveProfileResponse)
async def api_get_active_profile() -> ActiveProfileResponse:
    """Return the currently active profile name."""
    loop = asyncio.get_running_loop()
    name = await loop.run_in_executor(None, get_active_profile)
    return ActiveProfileResponse(name=name)


@router.post("", response_model=ProfileCreateResponse, status_code=201)
async def api_create_profile(
    payload: ProfileCreateRequest,
) -> ProfileCreateResponse:
    """Create a new profile."""
    loop = asyncio.get_running_loop()
    try:
        profile_dir = await loop.run_in_executor(
            None, partial(create_profile, payload.name)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # If a model was specified, write it to the profile's config.yaml
    if payload.model:
        await _set_profile_model(profile_dir, payload.model)

    return ProfileCreateResponse(name=payload.name, path=str(profile_dir))


@router.put("/active", response_model=ActiveProfileResponse)
async def api_switch_active_profile(
    payload: ProfileSwitchRequest,
) -> ActiveProfileResponse:
    """Switch the active profile."""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, partial(set_active_profile, payload.name))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ActiveProfileResponse(name=payload.name)


@router.delete("/{name}", response_model=ProfileDeleteResponse)
async def api_delete_profile(name: str) -> ProfileDeleteResponse:
    """Delete a profile by name."""
    loop = asyncio.get_running_loop()

    # Validate name first
    try:
        validate_profile_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if name == "default":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default profile (~/.hermes). Use: hermes uninstall",
        )

    if not profile_exists(name):
        raise HTTPException(status_code=404, detail=f"Profile '{name}' does not exist.")

    try:
        # Pass yes=True to skip interactive confirmation
        profile_dir = await loop.run_in_executor(
            None, partial(delete_profile, name, yes=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProfileDeleteResponse(ok=True, name=name, path=str(profile_dir))


async def _set_profile_model(profile_dir, model: str) -> None:
    """Write a model setting to the profile's config.yaml."""
    import yaml
    from pathlib import Path

    config_path = Path(profile_dir) / "config.yaml"

    def _write_model():
        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        config["model"] = {"default": model}
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _write_model)
