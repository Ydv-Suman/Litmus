from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from handlers import calculate_adjustment, publish_adjustment
from redis_client import get_redis_connection, subscribe_and_handle
from shared.schemas import FairnessAdjustment, HealthResponse, ResumeParsedEvent, Role


config = Config.from_env()


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def decode_token(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT header") from exc
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="Unsupported JWT algorithm")
    try:
        return jwt.decode(
            token,
            config.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT") from exc


def require_role(required_role: Role):
    async def dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> dict[str, Any]:
        token = _extract_token(authorization)
        claims = decode_token(token)
        if claims.get("role") != required_role.value:
            raise HTTPException(status_code=403, detail="Forbidden")
        return claims

    return dependency


async def consume_resume_event(raw_message: str) -> None:
    event = ResumeParsedEvent.model_validate_json(raw_message)
    result = calculate_adjustment(event)
    await publish_adjustment(redis_client=app.state.redis, result=result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_connection(config.redis_url)
    consumer_task = None
    if not config.sync_mode:
        consumer_task = asyncio.create_task(
            subscribe_and_handle(app.state.redis, "resume.parsed", consume_resume_event)
        )
    yield
    if consumer_task:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
    await app.state.redis.aclose()


app = FastAPI(title="Litmus - Fairness", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="fairness", details={"sync_mode": config.sync_mode})


@app.post("/internal/fairness/from-resume", response_model=FairnessAdjustment)
async def adjust_from_http(
    event: ResumeParsedEvent,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
) -> FairnessAdjustment:
    result = calculate_adjustment(event)
    if config.sync_mode:
        await publish_adjustment(redis_client=app.state.redis, result=result)
    return result

