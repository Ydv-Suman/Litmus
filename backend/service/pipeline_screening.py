"""
Pipeline screening score: resume vs job (0–20) plus optional LinkedIn URL validation (0–5).

If LinkedIn is omitted, it is not evaluated and max points exclude the LinkedIn band.
"""

from __future__ import annotations

import os
from typing import Any

RESUME_SCORE_MAX = 20.0
LINKEDIN_SCORE_MAX = 5.0

# Minimum fraction of (pipeline_max) required to continue to the technical assessment.
_DEFAULT_PASS_RATIO = 0.62


def _pass_threshold_ratio() -> float:
    try:
        return float(os.environ.get("PIPELINE_PASS_THRESHOLD_RATIO", str(_DEFAULT_PASS_RATIO)))
    except ValueError:
        return _DEFAULT_PASS_RATIO


def score_linkedin_url(url: str | None) -> tuple[float, float, dict[str, Any]]:
    """
    Returns (points, max_points_for_this_component, detail).
    Max is LINKEDIN_SCORE_MAX when the candidate supplied a URL we evaluate; 0 when omitted.
    """
    if url is None or not str(url).strip():
        return (
            0.0,
            0.0,
            {"evaluated": False, "note": "LinkedIn not provided; not included in screening cap."},
        )
    u = str(url).strip().rstrip("/")
    if _looks_like_linkedin_profile_path(u):
        return (
            LINKEDIN_SCORE_MAX,
            LINKEDIN_SCORE_MAX,
            {"evaluated": True, "valid_profile_shape": True},
        )
    return (
        0.0,
        LINKEDIN_SCORE_MAX,
        {
            "evaluated": True,
            "valid_profile_shape": False,
            "note": "LinkedIn URL did not match a typical public profile pattern.",
        },
    )


def _looks_like_linkedin_profile_path(url: str) -> bool:
    """Typical public profile or company: linkedin.com/... with /in/, /pub/, or /company/."""
    lower = url.lower()
    if "linkedin.com" not in lower:
        return False
    return (
        "/in/" in lower
        or "/pub/" in lower
        or "/company/" in lower
        or "/school/" in lower
    )


def compute_pipeline_screening(
    reality_match: dict[str, Any] | None,
    linkedin_url: str | None,
) -> dict[str, Any]:
    """
    Aggregate resume match total_points with optional LinkedIn component.

    pipeline_max = resume_max (usually 20) + linkedin band max (0 or 5).
    """
    resume_pts = 0.0
    resume_max = RESUME_SCORE_MAX
    if reality_match is not None:
        resume_pts = float(reality_match.get("total_points") or 0.0)
        resume_max = float(reality_match.get("max_points") or RESUME_SCORE_MAX)

    li_pts, li_max, li_detail = score_linkedin_url(linkedin_url)

    pipeline_max = resume_max + li_max
    pipeline_total = resume_pts + li_pts

    ratio = _pass_threshold_ratio()
    min_to_pass = round(pipeline_max * ratio, 2)
    passed = pipeline_total >= min_to_pass - 1e-6

    return {
        "pipeline_resume_points": round(resume_pts, 2),
        "pipeline_resume_max": resume_max,
        "pipeline_linkedin_points": round(li_pts, 2),
        "pipeline_linkedin_max": li_max,
        "linkedin_detail": li_detail,
        "pipeline_total": round(pipeline_total, 2),
        "pipeline_max": round(pipeline_max, 2),
        "pass_threshold_ratio": ratio,
        "minimum_points_to_pass": min_to_pass,
        "screening_passed": passed,
    }
