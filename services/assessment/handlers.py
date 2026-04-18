from __future__ import annotations

import anthropic
import redis.asyncio as redis

from shared.schemas import (
    AssessmentQuestionSet,
    AssessmentResult,
    AssessmentSubmission,
    ClaudeAssessmentGradeResult,
    ClaudeAssessmentQuestionResult,
    PipelineTopic,
    VerificationResult,
)


async def call_question_claude(
    *,
    client: anthropic.AsyncAnthropic,
    user_content: str,
) -> ClaudeAssessmentQuestionResult:
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=(
                "You are a component of the Litmus hiring platform. "
                "Your output will be parsed programmatically. "
                "Respond ONLY with valid JSON matching this schema: "
                '{"questions":[{"question_id":"00000000-0000-0000-0000-000000000000","prompt":"string","focus_area":"string"}]}. '
                "Do not include markdown, explanation, or any text outside the JSON."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return ClaudeAssessmentQuestionResult.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"Claude parse error: {type(exc).__name__}") from exc


async def call_grading_claude(
    *,
    client: anthropic.AsyncAnthropic,
    user_content: str,
) -> ClaudeAssessmentGradeResult:
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=(
                "You are a component of the Litmus hiring platform. "
                "Your output will be parsed programmatically. "
                "Respond ONLY with valid JSON matching this schema: "
                '{"graded_answers":[{"question_id":"00000000-0000-0000-0000-000000000000","score":0,"reasoning":"string"}],"overall_score":0}. '
                "Do not include markdown, explanation, or any text outside the JSON."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return ClaudeAssessmentGradeResult.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"Claude parse error: {type(exc).__name__}") from exc


async def generate_questions(
    *,
    client: anthropic.AsyncAnthropic,
    verification_result: VerificationResult,
) -> AssessmentQuestionSet:
    analysis = await call_question_claude(
        client=client,
        user_content=(
            "Generate five targeted assessment questions for skills that were not strongly verified. "
            "Verification result JSON:\n"
            f"{verification_result.model_dump_json()}"
        ),
    )
    return AssessmentQuestionSet(
        candidate_id=verification_result.candidate_id,
        job_id=verification_result.job_id,
        questions=analysis.questions,
    )


async def grade_submission(
    *,
    client: anthropic.AsyncAnthropic,
    question_set: AssessmentQuestionSet,
    submission: AssessmentSubmission,
) -> AssessmentResult:
    analysis = await call_grading_claude(
        client=client,
        user_content=(
            "Grade the candidate responses against the assessment questions. "
            "Question set JSON:\n"
            f"{question_set.model_dump_json()}\n"
            "Submission JSON:\n"
            f"{submission.model_dump_json()}"
        ),
    )
    return AssessmentResult(
        candidate_id=submission.candidate_id,
        job_id=submission.job_id,
        overall_score=analysis.overall_score,
        graded_answers=analysis.graded_answers,
    )


async def publish_assessment(
    *,
    redis_client: redis.Redis,
    result: AssessmentResult,
) -> None:
    await redis_client.publish(
        PipelineTopic.ASSESSMENT_COMPLETE.value,
        result.model_dump_json(),
    )

