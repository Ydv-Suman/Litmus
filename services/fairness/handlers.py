from __future__ import annotations

import redis.asyncio as redis

from shared.schemas import FairnessAdjustment, PipelineTopic, ResumeParsedEvent


def calculate_adjustment(event: ResumeParsedEvent) -> FairnessAdjustment:
    links = event.parsed_resume.links
    portfolio_count = len(
        [url for url in (links.github_url, links.linkedin_url, links.portfolio_url) if url]
    )
    adjusted = portfolio_count == 0
    verification_weight = 0.15 if adjusted else 0.30
    assessment_weight = 0.45 if adjusted else 0.30
    fairness_note = (
        "Candidate provided limited public portfolio evidence. Assessment weight increased to reduce portfolio-access bias."
        if adjusted
        else "Default weighting retained because public evidence was available for review."
    )
    return FairnessAdjustment(
        candidate_id=event.candidate_id,
        job_id=event.job_id,
        adjusted=adjusted,
        verification_weight=verification_weight,
        assessment_weight=assessment_weight,
        fairness_note=fairness_note,
    )


async def publish_adjustment(
    *,
    redis_client: redis.Redis,
    result: FairnessAdjustment,
) -> None:
    await redis_client.publish(
        PipelineTopic.FAIRNESS_ADJUSTED.value,
        result.model_dump_json(),
    )

