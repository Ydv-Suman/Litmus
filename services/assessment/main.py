from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any
from uuid import UUID

import anthropic
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from handlers import generate_questions, grade_submission, publish_assessment
from redis_client import get_redis_connection, subscribe_and_handle
from shared.schemas import (
    AssessmentQuestionSet,
    AssessmentResult,
    AssessmentSubmission,
    HealthResponse,
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


async def consume_verification_event(raw_message: str) -> None:
    verification_result = VerificationResult.model_validate_json(raw_message)
    question_set = await generate_questions(
        client=app.state.anthropic,
        verification_result=verification_result,
    )
    app.state.question_sets[str(question_set.candidate_id)] = question_set


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_connection(config.redis_url)
    app.state.anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    app.state.question_sets: dict[str, AssessmentQuestionSet] = {}
    app.state.submissions: set[tuple[str, str]] = set()
    consumer_task = None
    if not config.sync_mode:
        consumer_task = asyncio.create_task(
            subscribe_and_handle(
                app.state.redis,
                "verification.complete",
                consume_verification_event,
            )
        )
    yield
    if consumer_task:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
    await app.state.redis.aclose()


app = FastAPI(title="Litmus - Assessment", lifespan=lifespan)
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
        service="assessment",
        details={"sync_mode": config.sync_mode},
    )


@app.get("/internal/assessments/{candidate_id}", response_model=AssessmentQuestionSet)
async def get_questions(
    candidate_id: UUID,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
) -> AssessmentQuestionSet:
    question_set = app.state.question_sets.get(str(candidate_id))
    if question_set is None:
        raise HTTPException(status_code=404, detail="Assessment not ready")
    return question_set


@app.post("/internal/assessments/{candidate_id}/submit", response_model=AssessmentResult)
async def submit_answers(
    candidate_id: UUID,
    submission: AssessmentSubmission,
    _: dict[str, Any] = Depends(require_role(Role.APPLICANT)),
) -> AssessmentResult:
    if submission.candidate_id != candidate_id:
        raise HTTPException(status_code=400, detail="Candidate ID mismatch")
    dedupe_key = (str(submission.candidate_id), str(submission.job_id))
    if dedupe_key in app.state.submissions:
        raise HTTPException(
            status_code=409,
            detail="Assessment already submitted for this candidate and job",
        )
    question_set = app.state.question_sets.get(str(candidate_id))
    if question_set is None:
        raise HTTPException(status_code=404, detail="Assessment not ready")
    result = await grade_submission(
        client=app.state.anthropic,
        question_set=question_set,
        submission=submission,
    )
    app.state.submissions.add(dedupe_key)
    await publish_assessment(redis_client=app.state.redis, result=result)
    return result

