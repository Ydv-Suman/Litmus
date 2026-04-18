from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

import anthropic
import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from handlers import publish_verification, verify_candidate
from redis_client import get_redis_connection, subscribe_and_handle
from shared.schemas import HealthResponse, ResumeParsedEvent, Role, VerificationResult


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
    result = await verify_candidate(
        client=app.state.anthropic,
        http_client=app.state.http_client,
        event=event,
        github_token=config.github_token,
    )
    await publish_verification(redis_client=app.state.redis, result=result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_connection(config.redis_url)
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
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
    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(title="Litmus - Verification", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="verification",
        details={"sync_mode": config.sync_mode},
    )


@app.post("/internal/verification/from-resume", response_model=VerificationResult)
async def verify_from_http(
    event: ResumeParsedEvent,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
) -> VerificationResult:
    result = await verify_candidate(
        client=app.state.anthropic,
        http_client=app.state.http_client,
        event=event,
        github_token=config.github_token,
    )
    if config.sync_mode:
        await publish_verification(redis_client=app.state.redis, result=result)
    return result

