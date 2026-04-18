from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any, Callable
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi import Form
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from pydantic import ValidationError

from config import Config
from handlers import forward_json, forward_multipart
from shared.schemas import (
    AssessmentSubmission,
    CandidateLinks,
    HealthResponse,
    JobPostingCreate,
    ResumeSubmission,
    Role,
)


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


def require_role(required_role: Role) -> Callable[[str | None], dict[str, Any]]:
    async def dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> dict[str, Any]:
        token = _extract_token(authorization)
        claims = decode_token(token)
        if claims.get("role") != required_role.value:
            raise HTTPException(status_code=403, detail="Forbidden")
        return claims

    return dependency


def recruiter_key(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return get_remote_address(request)
    try:
        token = _extract_token(authorization)
        claims = decode_token(token)
    except HTTPException:
        return get_remote_address(request)
    return str(claims["sub"])


limiter = Limiter(key_func=get_remote_address, default_limits=[])
recruiter_limiter = Limiter(key_func=recruiter_key, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Litmus - Gateway", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="gateway")


@app.post("/api/v1/applications")
@limiter.limit(config.applicant_rate_limit)
async def submit_application(
    request: Request,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    job_id: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    github_url: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    portfolio_url: Annotated[str | None, Form()] = None,
    resume: UploadFile = File(...),
) -> Any:
    del request
    token = _extract_token(authorization)
    try:
        ResumeSubmission(
            job_id=UUID(job_id),
            name=name,
            email=email,
            links=CandidateLinks(
                github_url=github_url or None,
                linkedin_url=linkedin_url or None,
                portfolio_url=portfolio_url or None,
            ),
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    content = await resume.read()
    status_code, payload = await forward_multipart(
        client=app.state.http_client,
        base_url=config.ingestion_service_url,
        path="/internal/applications",
        token=token,
        form_data={
            "job_id": job_id,
            "name": name,
            "email": email,
            "github_url": github_url or "",
            "linkedin_url": linkedin_url or "",
            "portfolio_url": portfolio_url or "",
        },
        filename=resume.filename or "resume.pdf",
        content=content,
        content_type=resume.content_type or "application/octet-stream",
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return payload


@app.get("/api/v1/assessments/{candidate_id}")
@limiter.limit(config.applicant_rate_limit)
async def get_assessment(
    request: Request,
    candidate_id: str,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Any:
    del request
    token = _extract_token(authorization)
    status_code, payload = await forward_json(
        client=app.state.http_client,
        method="GET",
        base_url=config.assessment_service_url,
        path=f"/internal/assessments/{candidate_id}",
        token=token,
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return payload


@app.post("/api/v1/assessments/{candidate_id}/submit")
@limiter.limit(config.applicant_rate_limit)
async def submit_assessment(
    request: Request,
    candidate_id: str,
    submission: AssessmentSubmission,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Any:
    del request
    token = _extract_token(authorization)
    if candidate_id != str(submission.candidate_id):
        raise HTTPException(status_code=400, detail="Candidate ID mismatch")
    status_code, payload = await forward_json(
        client=app.state.http_client,
        method="POST",
        base_url=config.assessment_service_url,
        path=f"/internal/assessments/{candidate_id}/submit",
        token=token,
        payload=submission.model_dump(mode="json"),
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return payload


@app.post("/api/v1/jobs")
@recruiter_limiter.limit(config.recruiter_rate_limit)
async def create_job(
    request: Request,
    payload: JobPostingCreate,
    claims: dict[str, Any] = Depends(require_role(Role.RECRUITER)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Any:
    del request
    token = _extract_token(authorization)
    status_code, response_payload = await forward_json(
        client=app.state.http_client,
        method="POST",
        base_url=config.scoring_service_url,
        path="/internal/jobs",
        token=token,
        payload=payload.model_dump(mode="json"),
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=response_payload)
    return response_payload


@app.get("/api/v1/jobs/{job_id}/candidates")
@recruiter_limiter.limit(config.recruiter_rate_limit)
async def list_candidates(
    request: Request,
    job_id: str,
    _: dict[str, Any] = Depends(require_role(Role.RECRUITER)),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Any:
    del request
    token = _extract_token(authorization)
    status_code, payload = await forward_json(
        client=app.state.http_client,
        method="GET",
        base_url=config.scoring_service_url,
        path=f"/internal/jobs/{job_id}/candidates",
        token=token,
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return payload
