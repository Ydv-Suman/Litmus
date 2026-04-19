"""
Aggregate screening score across resume, GitHub, and LinkedIn analyses.

Each component contributes its actual scored points and max points when available.
The applicant advances to the assessment when pipeline_total / pipeline_max meets
the configured pass threshold.
"""

from __future__ import annotations

import os
from typing import Any

RESUME_SCORE_MAX = 20.0
GITHUB_SCORE_MAX = 40.0
LINKEDIN_SCORE_MAX = 30.0

_DEFAULT_PASS_RATIO = 0.62


def _pass_threshold_ratio() -> float:
    try:
        return float(os.environ.get("PIPELINE_PASS_THRESHOLD_RATIO", str(_DEFAULT_PASS_RATIO)))
    except ValueError:
        return _DEFAULT_PASS_RATIO


def _component_points_max(
    payload: dict[str, Any] | None,
    *,
    default_max: float,
    missing_note: str,
) -> tuple[float, float, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 0.0, 0.0, {"evaluated": False, "note": missing_note}

    points = float(payload.get("points") or payload.get("total_points") or 0.0)
    max_points = float(payload.get("max_points") or default_max or 0.0)
    return points, max_points, {"evaluated": True}


def compute_pipeline_screening(
    reality_match: dict[str, Any] | None,
    github_analysis: dict[str, Any] | None,
    linkedin_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    resume_pts, resume_max, resume_detail = _component_points_max(
        reality_match,
        default_max=RESUME_SCORE_MAX,
        missing_note="Resume-to-job analysis was unavailable.",
    )
    github_pts, github_max, github_detail = _component_points_max(
        github_analysis,
        default_max=GITHUB_SCORE_MAX,
        missing_note="GitHub analysis was unavailable.",
    )
    linkedin_pts, linkedin_max, linkedin_detail = _component_points_max(
        linkedin_analysis,
        default_max=LINKEDIN_SCORE_MAX,
        missing_note="LinkedIn analysis was unavailable.",
    )

    pipeline_total = resume_pts + github_pts + linkedin_pts
    pipeline_max = resume_max + github_max + linkedin_max
    ratio = _pass_threshold_ratio()
    minimum_points_to_pass = round(pipeline_max * ratio, 2) if pipeline_max > 0 else 0.0
    screening_passed = pipeline_total >= minimum_points_to_pass - 1e-6 if pipeline_max > 0 else False

    return {
        "pipeline_resume_points": round(resume_pts, 2),
        "pipeline_resume_max": round(resume_max, 2),
        "pipeline_github_points": round(github_pts, 2),
        "pipeline_github_max": round(github_max, 2),
        "pipeline_linkedin_points": round(linkedin_pts, 2),
        "pipeline_linkedin_max": round(linkedin_max, 2),
        "resume_detail": resume_detail,
        "github_detail": github_detail,
        "linkedin_detail": linkedin_detail,
        "pipeline_total": round(pipeline_total, 2),
        "pipeline_max": round(pipeline_max, 2),
        "pass_threshold_ratio": ratio,
        "minimum_points_to_pass": minimum_points_to_pass,
        "screening_passed": screening_passed,
    }
