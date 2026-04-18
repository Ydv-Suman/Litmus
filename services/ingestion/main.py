from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

import anthropic
import httpx
import jwt
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from handlers import (
    build_parsed_resume,
    dispatch_resume,
    validate_and_parse_resume,
    validate_external_url,
)
from redis_client import get_redis_connection
from shared.schemas import ApplicationAcceptedResponse, CandidateLinks, HealthResponse, ResumeSubmission, Role


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_connection(config.redis_url)
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    yield
    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(title="Litmus - Ingestion", lifespan=lifespan)
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
        service="ingestion",
        details={"sync_mode": config.sync_mode},
    )


@app.post("/internal/applications", response_model=ApplicationAcceptedResponse)
async def create_application(
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    job_id: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    github_url: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    portfolio_url: Annotated[str | None, Form()] = None,
    resume: UploadFile = File(...),
) -> ApplicationAcceptedResponse:
    token = _extract_token(authorization)
    try:
        links = CandidateLinks(
            github_url=validate_external_url(github_url),
            linkedin_url=validate_external_url(linkedin_url),
            portfolio_url=validate_external_url(portfolio_url),
        )
        submission = ResumeSubmission(
            job_id=UUID(job_id),
            name=name,
            email=email,
            links=links,
        )
        resume_text = await validate_and_parse_resume(
            await resume.read(),
            resume.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed_resume = await build_parsed_resume(
        client=app.state.anthropic,
        submission=submission,
        resume_text=resume_text,
    )
    await dispatch_resume(
        config=config,
        redis_client=app.state.redis,
        http_client=app.state.http_client,
        parsed_resume=parsed_resume,
        token=token,
    )
    return ApplicationAcceptedResponse(
        candidate_id=parsed_resume.candidate_id,
        job_id=parsed_resume.job_id,
        status="submitted",
        message="Application accepted for asynchronous processing.",
    )

