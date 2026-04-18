from __future__ import annotations

import anthropic
import redis.asyncio as redis

from shared.schemas import ClaudeFitAnalysis, FitScoreResult, PipelineTopic, ResumeParsedEvent


async def call_claude(
    *,
    client: anthropic.AsyncAnthropic,
    user_content: str,
) -> ClaudeFitAnalysis:
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=(
                "You are a component of the Litmus hiring platform. "
                "Your output will be parsed programmatically. "
                "Respond ONLY with valid JSON matching this schema: "
                '{"fit_score":0,"matched_skills":["string"],"missing_skills":["string"],"seniority_match":"string","rationale_summary":"string"}. '
                "Do not include markdown, explanation, or any text outside the JSON."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return ClaudeFitAnalysis.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"Claude parse error: {type(exc).__name__}") from exc


async def score_fit(
    *,
    client: anthropic.AsyncAnthropic,
    event: ResumeParsedEvent,
) -> FitScoreResult:
    analysis = await call_claude(
        client=client,
        user_content=(
            "Assess candidate fit from the parsed resume. "
            "If no job description context is available yet, score only the internal coherence of the resume and documented skills. "
            "Parsed resume JSON:\n"
            f"{event.parsed_resume.model_dump_json()}"
        ),
    )
    return FitScoreResult(
        candidate_id=event.candidate_id,
        job_id=event.job_id,
        fit_score=analysis.fit_score,
        matched_skills=analysis.matched_skills,
        missing_skills=analysis.missing_skills,
        seniority_match=analysis.seniority_match,
        rationale_summary=analysis.rationale_summary,
    )


async def publish_fit_score(
    *,
    redis_client: redis.Redis,
    result: FitScoreResult,
) -> None:
    await redis_client.publish(PipelineTopic.FIT_SCORED.value, result.model_dump_json())

