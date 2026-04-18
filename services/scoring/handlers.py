from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as redis
from supabase import Client, create_client

from shared.schemas import (
    AssessmentResult,
    CandidateListResponse,
    CandidateScore,
    FairnessAdjustment,
    FinalScoreEvent,
    FitScoreResult,
    JobPosting,
    VerificationResult,
)


def build_supabase_client(supabase_url: str, supabase_key: str) -> Client:
    return create_client(supabase_url, supabase_key)


def build_candidate_score(
    *,
    fit_result: FitScoreResult,
    verification_result: VerificationResult,
    fairness_result: FairnessAdjustment,
    assessment_result: AssessmentResult,
) -> CandidateScore:
    consistency_score = max(0.0, 100.0 - (len(verification_result.flagged_inconsistencies) * 10))
    final_score = (
        (fit_result.fit_score * 0.30)
        + (verification_result.overall_confidence * fairness_result.verification_weight)
        + (assessment_result.overall_score * fairness_result.assessment_weight)
        + (consistency_score * 0.10)
    )
    return CandidateScore(
        candidate_id=fit_result.candidate_id,
        job_id=fit_result.job_id,
        fit_score=fit_result.fit_score,
        verification_score=verification_result.overall_confidence,
        assessment_score=assessment_result.overall_score,
        final_score=round(min(final_score, 100.0), 2),
        fairness_note=fairness_result.fairness_note,
    )


async def persist_job(
    *,
    supabase: Client,
    job: JobPosting,
) -> None:
    await asyncio.to_thread(
        lambda: supabase.table("jobs").upsert(job.model_dump(mode="json")).execute()
    )


async def persist_score(
    *,
    supabase: Client,
    score: CandidateScore,
) -> None:
    await asyncio.to_thread(
        lambda: supabase.table("candidate_scores")
        .upsert(score.model_dump(mode="json"))
        .execute()
    )


async def publish_final_score(
    *,
    redis_client: redis.Redis,
    score: CandidateScore,
) -> None:
    event = FinalScoreEvent(score=score)
    await redis_client.publish(event.topic.value, event.model_dump_json())


def list_candidates_for_job(
    *,
    job_id: str,
    scores: dict[str, CandidateScore],
) -> CandidateListResponse:
    candidates = [
        candidate_score
        for candidate_score in scores.values()
        if str(candidate_score.job_id) == job_id
    ]
    candidates.sort(key=lambda item: item.final_score, reverse=True)
    return CandidateListResponse(job_id=job_id, candidates=candidates)


def merge_partial(state: dict[str, dict[str, Any]], key: str, field: str, value: Any) -> None:
    state.setdefault(key, {})
    state[key][field] = value

