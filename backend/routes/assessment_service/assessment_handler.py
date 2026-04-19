"""Fetch, run, and submit technical assessments by secret token."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived
from service.assessment_generator import strip_assessment_answers_for_candidate

router = APIRouter(prefix="/assessment", tags=["assessment"])


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AssessmentSubmissionPayload(BaseModel):
    mcq_answers: dict[str, str] = Field(default_factory=dict)
    coding_answer: str = ""
    coding_language: str = ""


class AssessmentRunPayload(BaseModel):
    coding_answer: str = ""
    coding_language: str = ""


def _get_assessment_row_or_404(db: Session, token: str) -> ApplicationReceived:
    row = (
        db.query(ApplicationReceived)
        .filter(
            ApplicationReceived.assessment_token == token,
            ApplicationReceived.is_deleted.is_(False),
        )
        .first()
    )
    if not row or not row.assessment_payload:
        raise HTTPException(
            status_code=404,
            detail="Assessment not found or no longer available.",
        )
    return row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_submission_snapshot(row: ApplicationReceived) -> dict[str, Any] | None:
    payload = row.assessment_candidate_answers
    return payload if isinstance(payload, dict) else None


def _grading_notes(assessment_payload: dict[str, Any]) -> dict[str, Any]:
    notes = assessment_payload.get("grading_notes") or {}
    return notes if isinstance(notes, dict) else {}


def _mcq_score(
    assessment_payload: dict[str, Any],
    mcq_answers: dict[str, str],
) -> tuple[float, float, list[dict[str, Any]]]:
    mcq_items = assessment_payload.get("part1_mcq") or []
    notes = _grading_notes(assessment_payload)
    points_each = float(notes.get("mcq_points_each") or 5.0)
    max_points = float(notes.get("mcq_total") or (len(mcq_items) * points_each))
    earned = 0.0
    details: list[dict[str, Any]] = []

    for item in mcq_items:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("id"))
        submitted_answer = str(mcq_answers.get(question_id, "")).strip().upper()
        correct_answer = str(item.get("correct", "")).strip().upper()
        passed = bool(
            submitted_answer and correct_answer and submitted_answer == correct_answer
        )
        if passed:
            earned += points_each
        details.append(
            {
                "id": item.get("id"),
                "submitted": submitted_answer,
                "correct": correct_answer,
                "passed": passed,
            }
        )

    return round(earned, 2), round(max_points, 2), details


def _coding_score(
    assessment_payload: dict[str, Any],
    run_result: dict[str, Any],
) -> tuple[float, float]:
    notes = _grading_notes(assessment_payload)
    max_points = float(notes.get("coding_points_total") or 50.0)
    total_count = float(run_result.get("total_count") or 0.0)
    passed_count = float(run_result.get("passed_count") or 0.0)
    if total_count <= 0:
        return 0.0, round(max_points, 2)
    score = max_points * (passed_count / total_count)
    return round(score, 2), round(max_points, 2)


def _combined_final_score(
    row: ApplicationReceived,
    assessment_total_score: float,
    assessment_total_max: float,
) -> tuple[float, float]:
    screening_ratio = (
        (float(row.pipeline_total or 0.0) / float(row.pipeline_max or 1.0))
        if float(row.pipeline_max or 0.0) > 0
        else 0.0
    )
    assessment_ratio = (
        (assessment_total_score / assessment_total_max)
        if assessment_total_max > 0
        else 0.0
    )
    final_score = (screening_ratio * 100.0 * 0.6) + (assessment_ratio * 100.0 * 0.4)
    return round(final_score, 2), 100.0


def _coerce_public_test_cases(assessment_payload: dict[str, Any]) -> list[dict[str, Any]]:
    coding = assessment_payload.get("part2_coding") or {}
    test_cases = coding.get("test_cases") or []
    output: list[dict[str, Any]] = []
    for case in test_cases:
        if not isinstance(case, dict):
            continue
        output.append(
            {
                "name": case.get("name"),
                "description": case.get("description"),
                "input": case.get("input"),
                "expected_output": case.get("expected_output"),
            }
        )
    return output


def _run_coding_submission(
    assessment_payload: dict[str, Any],
    coding_answer: str,
    coding_language: str,
) -> dict[str, Any]:
    coding = assessment_payload.get("part2_coding") or {}
    function_name = str(coding.get("function_name") or "").strip()
    test_cases = _coerce_public_test_cases(assessment_payload)
    if not function_name or not test_cases:
        raise HTTPException(
            status_code=400,
            detail="This assessment does not include runnable coding metadata.",
        )

    normalized_language = str(coding_language or coding.get("language") or "").strip().lower()
    if normalized_language not in {"javascript", "python"}:
        raise HTTPException(
            status_code=400,
            detail="Only javascript and python coding runs are supported.",
        )

    if normalized_language == "javascript":
        return _run_javascript_submission(function_name, coding_answer, test_cases)
    return _run_python_submission(function_name, coding_answer, test_cases)


def _run_javascript_submission(
    function_name: str,
    coding_answer: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    runner_source = f"""
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[2], 'utf8');
const fnName = {json.dumps(function_name)};
const tests = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const sandbox = {{ module: {{ exports: {{}} }}, exports: {{}}, console }};
vm.createContext(sandbox);
vm.runInContext(code, sandbox, {{ timeout: 1500 }});

let candidate = sandbox[fnName];
if (typeof candidate !== 'function' && sandbox.module && sandbox.module.exports) {{
  if (typeof sandbox.module.exports === 'function') {{
    candidate = sandbox.module.exports;
  }} else if (typeof sandbox.module.exports[fnName] === 'function') {{
    candidate = sandbox.module.exports[fnName];
  }}
}}

if (typeof candidate !== 'function') {{
  throw new Error(`Function "${{fnName}}" was not defined.`);
}}

const results = tests.map((test) => {{
  const args = Array.isArray(test.input) ? test.input : [test.input];
  const actual = candidate(...args);
  const passed = JSON.stringify(actual) === JSON.stringify(test.expected_output);
  return {{
    name: test.name,
    description: test.description,
    passed,
    actual,
    expected_output: test.expected_output
  }};
}});

process.stdout.write(JSON.stringify({{
  passed_count: results.filter((item) => item.passed).length,
  total_count: results.length,
  results
}}));
"""

    return _run_code_process(
        runtime_command="node",
        source_suffix=".js",
        source_content=coding_answer,
        runner_suffix=".cjs",
        runner_content=runner_source,
        test_cases=test_cases,
    )


def _run_python_submission(
    function_name: str,
    coding_answer: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    runner_source = f"""
import importlib.util
import json
import sys

fn_name = {function_name!r}
source_path = sys.argv[1]
tests_path = sys.argv[2]

spec = importlib.util.spec_from_file_location("candidate_solution", source_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

candidate = getattr(module, fn_name, None)
if not callable(candidate):
    raise RuntimeError(f'Function "{{fn_name}}" was not defined.')

with open(tests_path, "r", encoding="utf-8") as handle:
    tests = json.load(handle)

results = []
for test in tests:
    raw_input = test.get("input")
    args = raw_input if isinstance(raw_input, list) else [raw_input]
    actual = candidate(*args)
    passed = actual == test.get("expected_output")
    results.append({{
        "name": test.get("name"),
        "description": test.get("description"),
        "passed": passed,
        "actual": actual,
        "expected_output": test.get("expected_output"),
    }})

print(json.dumps({{
    "passed_count": len([item for item in results if item["passed"]]),
    "total_count": len(results),
    "results": results,
}}))
"""

    return _run_code_process(
        runtime_command="python3",
        source_suffix=".py",
        source_content=coding_answer,
        runner_suffix="_runner.py",
        runner_content=runner_source,
        test_cases=test_cases,
    )


def _run_code_process(
    *,
    runtime_command: str,
    source_suffix: str,
    source_content: str,
    runner_suffix: str,
    runner_content: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="litmus-assessment-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / f"candidate{source_suffix}"
        tests_path = temp_path / "tests.json"
        runner_path = temp_path / f"runner{runner_suffix}"
        source_path.write_text(source_content, encoding="utf-8")
        tests_path.write_text(json.dumps(test_cases), encoding="utf-8")
        runner_path.write_text(runner_content, encoding="utf-8")

        try:
            completed = subprocess.run(
                [runtime_command, str(runner_path), str(source_path), str(tests_path)],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"{runtime_command} runtime is not available on the server.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=408, detail="Code execution timed out.") from exc

        if completed.returncode != 0:
            error_message = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Code execution failed."
            )
            return {
                "status": "runtime_error",
                "passed_count": 0,
                "total_count": len(test_cases),
                "results": [],
                "error": error_message,
            }

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500,
                detail="Code runner returned invalid output.",
            ) from exc
        payload["status"] = "ok"
        return payload


@router.get("/{token}")
def get_assessment_for_candidate(
    token: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _get_assessment_row_or_404(db, token)

    return {
        "application_id": row.id,
        "job_id": row.job_id,
        "assessment": strip_assessment_answers_for_candidate(row.assessment_payload),
        "candidate_submission": _candidate_submission_snapshot(row),
        "status": row.status,
        "scores": {
            "pipeline_total": row.pipeline_total,
            "pipeline_max": row.pipeline_max,
            "assessment_mcq_score": row.assessment_mcq_score,
            "assessment_mcq_max": row.assessment_mcq_max,
            "assessment_coding_score": row.assessment_coding_score,
            "assessment_coding_max": row.assessment_coding_max,
            "assessment_total_score": row.assessment_total_score,
            "assessment_total_max": row.assessment_total_max,
            "final_score": row.final_score,
            "final_score_max": row.final_score_max,
        },
    }


@router.post("/{token}/run")
def run_assessment_code(
    token: str,
    payload: AssessmentRunPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _get_assessment_row_or_404(db, token)
    result = _run_coding_submission(
        row.assessment_payload,
        payload.coding_answer,
        payload.coding_language,
    )
    return {
        "application_id": row.id,
        "result": result,
    }


@router.post("/{token}/submit")
def submit_assessment_for_candidate(
    token: str,
    payload: AssessmentSubmissionPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _get_assessment_row_or_404(db, token)
    submitted_at = datetime.now(timezone.utc)
    run_result = _run_coding_submission(
        row.assessment_payload,
        payload.coding_answer,
        payload.coding_language,
    )
    mcq_score, mcq_max, mcq_details = _mcq_score(
        row.assessment_payload,
        payload.mcq_answers,
    )
    coding_score, coding_max = _coding_score(row.assessment_payload, run_result)
    assessment_total_score = round(mcq_score + coding_score, 2)
    assessment_total_max = round(mcq_max + coding_max, 2)
    final_score, final_score_max = _combined_final_score(
        row,
        assessment_total_score,
        assessment_total_max,
    )
    stored_payload = {
        "mcq_answers": payload.mcq_answers,
        "coding_answer": payload.coding_answer,
        "coding_language": payload.coding_language
        or ((row.assessment_payload.get("part2_coding") or {}).get("language") or ""),
        "submitted_at": _now_iso(),
        "mcq_result": {
            "score": mcq_score,
            "max": mcq_max,
            "details": mcq_details,
        },
        "coding_result": run_result,
    }
    row.assessment_candidate_answers = stored_payload
    row.assessment_run_result = run_result
    row.assessment_mcq_score = mcq_score
    row.assessment_mcq_max = mcq_max
    row.assessment_coding_score = coding_score
    row.assessment_coding_max = coding_max
    row.assessment_total_score = assessment_total_score
    row.assessment_total_max = assessment_total_max
    row.assessment_score = assessment_total_score
    row.assessment_answers = payload.mcq_answers
    row.final_score = final_score
    row.final_score_max = final_score_max
    row.assessment_submitted_at = submitted_at
    row.status = "assessment_submitted"
    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save assessment answers.",
        ) from exc

    return {
        "message": "Assessment answers submitted successfully.",
        "application_id": row.id,
        "submitted_at": submitted_at.isoformat(),
        "status": row.status,
        "scores": {
            "assessment_mcq_score": mcq_score,
            "assessment_mcq_max": mcq_max,
            "assessment_coding_score": coding_score,
            "assessment_coding_max": coding_max,
            "assessment_total_score": assessment_total_score,
            "assessment_total_max": assessment_total_max,
            "final_score": final_score,
            "final_score_max": final_score_max,
        },
    }
