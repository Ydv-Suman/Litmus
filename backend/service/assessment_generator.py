"""
Generate a technical assessment (Part 1: MCQ, Part 2: coding challenge) using Groq.

JSON schema aligns with the product spec: 10 MCQs (5 pts each when graded later),
coding challenge with starter code and test-case descriptions (50 pts when graded).
Final combined score formula is documented in the payload for downstream use:
  final = pipeline_score * 0.6 + assessment_score * 0.4
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from models.job_listing import JobListing


def _groq_key_and_model() -> tuple[str, str]:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("Set GROQ_API_KEY in backend/.env to generate assessments.")
    model = (
        os.environ.get("GROQ_MODEL")
        or os.environ.get("LLM_MODEL")
        or "llama-3.3-70b-versatile"
    )
    return key, model


def _groq_json(prompt: str, *, timeout_s: float = 120.0) -> str:
    from groq import Groq

    api_key, model = _groq_key_and_model()
    client = Groq(api_key=api_key)
    system_msg = (
        "You reply with a single valid JSON object only. No markdown fences, no commentary."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.35,
            timeout=timeout_s,
            max_completion_tokens=8192,
            response_format={"type": "json_object"},
        )
    except Exception:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.35,
            timeout=timeout_s,
            max_completion_tokens=8192,
        )
    if not completion.choices:
        raise RuntimeError("Groq returned no choices for assessment generation.")
    content = completion.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("Groq returned empty assessment content.")
    return content


def _strip_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _skills_hint(job: JobListing) -> str:
    rs = job.required_skills
    if isinstance(rs, list):
        return ", ".join(str(x) for x in rs if x)
    if isinstance(rs, dict):
        parts: list[str] = []
        for v in rs.values():
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
            elif v:
                parts.append(str(v))
        return ", ".join(parts)
    return ""


def _validate_payload(data: dict[str, Any]) -> None:
    mcq = data.get("part1_mcq")
    if not isinstance(mcq, list) or len(mcq) != 10:
        raise ValueError("Assessment must include part1_mcq with exactly 10 questions.")
    for i, q in enumerate(mcq):
        if not isinstance(q, dict):
            raise ValueError(f"part1_mcq[{i}] must be an object.")
        for key in ("question", "options", "correct", "explanation"):
            if key not in q:
                raise ValueError(f"part1_mcq[{i}] missing {key}.")
        opts = q.get("options")
        if not isinstance(opts, dict) or not {"A", "B", "C", "D"}.issubset(set(opts.keys())):
            raise ValueError(f"part1_mcq[{i}] options must include A,B,C,D.")

    part2 = data.get("part2_coding")
    if not isinstance(part2, dict):
        raise ValueError("part2_coding must be an object.")
    for key in ("title", "instructions", "starter_code", "test_cases"):
        if key not in part2:
            raise ValueError(f"part2_coding missing {key}.")
    tc = part2.get("test_cases")
    if not isinstance(tc, list) or len(tc) < 5:
        raise ValueError("part2_coding.test_cases must list at least 5 test cases.")


def build_assessment_prompt(job: JobListing) -> str:
    skills = _skills_hint(job)
    return f"""Generate a technical assessment for this role.

Job title: {job.title}
Required stack / skills: {skills}
Seniority / level: {job.experience_level}
Department: {job.department}

Job description (use for targeting topics only):
{job.description[:6000]}

Return a single JSON object with exactly this structure:
{{
  "part1_mcq": [
    {{
      "id": 1,
      "topic": "e.g. React or TypeScript or Node",
      "question": "clear question text",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct": "A single letter A|B|C|D",
      "explanation": "one or two sentences why the answer is correct"
    }}
  ],
  "part2_coding": {{
    "title": "short title",
    "language": "javascript|typescript|python",
    "time_limit_minutes": 40,
    "instructions": "full problem statement including constraints",
    "starter_code": "plain code as a string (escape newlines as needed in JSON)",
    "test_cases": [
      {{"name": "t1", "description": "what is asserted"}}
    ]
  }},
  "grading_notes": {{
    "mcq_points_each": 5,
    "mcq_total": 50,
    "coding_points_total": 50,
    "assessment_total": 100,
    "final_score_formula": "final = pipeline_score * 0.6 + assessment_score * 0.4"
  }}
}}

Rules:
- Exactly 10 MCQ items in part1_mcq, numbered id 1..10.
- Questions must be specific to the stack listed above, not generic trivia.
- Each MCQ must have four distinct options and one correct letter.
- part2_coding: one medium-difficulty problem appropriate to the role; include exactly 5 entries in test_cases describing checks (e.g. edge cases).
- Do not include markdown code fences inside JSON string values.
"""


def generate_technical_assessment(job: JobListing) -> dict[str, Any]:
    raw = _groq_json(build_assessment_prompt(job))
    try:
        data = json.loads(_strip_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Assessment JSON parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Assessment root must be an object.")
    _validate_payload(data)
    data.setdefault(
        "meta",
        {
            "job_id": job.id,
            "job_title": job.title,
            "experience_level": job.experience_level,
        },
    )
    return data


def strip_assessment_answers_for_candidate(assessment: dict[str, Any]) -> dict[str, Any]:
    """Remove MCQ answer key so the candidate endpoint does not leak correct options."""
    public = copy.deepcopy(assessment)
    for q in public.get("part1_mcq") or []:
        if isinstance(q, dict):
            q.pop("correct", None)
            q.pop("explanation", None)
    gn = public.get("grading_notes")
    if isinstance(gn, dict):
        gn.pop("mcq_points_each", None)
    return public
