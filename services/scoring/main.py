from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from handlers import (
    build_candidate_score,
    build_supabase_client,
    list_candidates_for_job,
    merge_partial,
    persist_job,
    persist_score,
    publish_final_score,
)
from redis_client import get_redis_connection, subscribe_and_handle
from shared.schemas import (
    AssessmentResult,
    CandidateListResponse,
    CandidateScore,
    FitScoreResult,
    FairnessAdjustment,
    HealthResponse,
    JobCreateResponse,
    JobPostingCreate,
    JobPosting,
    Role,
    VerificationResult,
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


async def _attempt_finalize(candidate_id: str) -> None:
    partial = app.state.pipeline_state.get(candidate_id, {})
    required_fields = {"fit", "verification", "fairness", "assessment"}
    if not required_fields.issubset(partial):
        return
    score = build_candidate_score(
        fit_result=partial["fit"],
        verification_result=partial["verification"],
        fairness_result=partial["fairness"],
        assessment_result=partial["assessment"],
    )
    app.state.scores[candidate_id] = score
    await persist_score(supabase=app.state.supabase, score=score)
    await publish_final_score(redis_client=app.state.redis, score=score)


async def consume_fit(raw_message: str) -> None:
    result = FitScoreResult.model_validate_json(raw_message)
    merge_partial(app.state.pipeline_state, str(result.candidate_id), "fit", result)
    await _attempt_finalize(str(result.candidate_id))


async def consume_verification(raw_message: str) -> None:
    result = VerificationResult.model_validate_json(raw_message)
    merge_partial(
        app.state.pipeline_state,
        str(result.candidate_id),
        "verification",
        result,
    )
    await _attempt_finalize(str(result.candidate_id))


async def consume_fairness(raw_message: str) -> None:
    result = FairnessAdjustment.model_validate_json(raw_message)
    merge_partial(app.state.pipeline_state, str(result.candidate_id), "fairness", result)
    await _attempt_finalize(str(result.candidate_id))


async def consume_assessment(raw_message: str) -> None:
    result = AssessmentResult.model_validate_json(raw_message)
    merge_partial(
        app.state.pipeline_state,
        str(result.candidate_id),
        "assessment",
        result,
    )
    await _attempt_finalize(str(result.candidate_id))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_connection(config.redis_url)
    app.state.supabase = build_supabase_client(config.supabase_url, config.supabase_key)
    app.state.jobs: dict[str, JobPosting] = {}
    app.state.scores: dict[str, CandidateScore] = {}
    app.state.pipeline_state: dict[str, dict[str, Any]] = {}
    consumer_tasks = []
    if not config.sync_mode:
        consumer_tasks = [
            asyncio.create_task(
                subscribe_and_handle(app.state.redis, "fit.scored", consume_fit)
            ),
            asyncio.create_task(
                subscribe_and_handle(
                    app.state.redis,
                    "verification.complete",
                    consume_verification,
                )
            ),
            asyncio.create_task(
                subscribe_and_handle(
                    app.state.redis,
                    "fairness.adjusted",
                    consume_fairness,
                )
            ),
            asyncio.create_task(
                subscribe_and_handle(
                    app.state.redis,
                    "assessment.complete",
                    consume_assessment,
                )
            ),
        ]
    yield
    for task in consumer_tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await app.state.redis.aclose()


app = FastAPI(title="Litmus - Scoring", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="scoring", details={"sync_mode": config.sync_mode})


@app.post("/internal/jobs", response_model=JobCreateResponse)
async def create_job(
    payload: JobPostingCreate,
    claims: dict[str, Any] = Depends(require_role(Role.RECRUITER)),
) -> JobCreateResponse:
    job = JobPosting(
        recruiter_id=str(claims["sub"]),
        title=payload.title,
        description=payload.description,
    )
    app.state.jobs[str(job.job_id)] = job
    await persist_job(supabase=app.state.supabase, job=job)
    return JobCreateResponse(job=job)


@app.get("/internal/jobs/{job_id}/candidates", response_model=CandidateListResponse)
async def list_candidates(
    job_id: UUID,
    _: dict[str, Any] = Depends(require_role(Role.RECRUITER)),
) -> CandidateListResponse:
    return list_candidates_for_job(job_id=str(job_id), scores=app.state.scores)
