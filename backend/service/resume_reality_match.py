"""
Compare parsed resume to the job listing from the database (description, required skills, experience level).
No GitHub or LinkedIn — text overlap and simple experience-band fit only.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from models.job_listing import JobListing

_SKILLS_MAX = 12
_EXPERIENCE_MAX = 8
_TOTAL_MAX = _SKILLS_MAX + _EXPERIENCE_MAX


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _flatten_resume_skills(resume_parsed: dict[str, Any] | None) -> set[str]:
    if not resume_parsed:
        return set()
    skills = resume_parsed.get("skills") or {}
    out: set[str] = set()
    if isinstance(skills, dict):
        for bucket in skills.values():
            if isinstance(bucket, list):
                for x in bucket:
                    if x and str(x).strip():
                        out.add(_norm(x))
    for exp in resume_parsed.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        for t in exp.get("technologies_used") or []:
            if t and str(t).strip():
                out.add(_norm(t))
    for proj in resume_parsed.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        for t in proj.get("technologies") or []:
            if t and str(t).strip():
                out.add(_norm(t))
    return {s for s in out if len(s) >= 2}


def _resume_search_blob(resume_parsed: dict[str, Any] | None) -> str:
    """Single lowercase string of resume content for substring / token checks."""
    if not resume_parsed:
        return ""
    parts: list[str] = []
    for key in ("summary", "name", "current_title", "location"):
        v = resume_parsed.get(key)
        if v:
            parts.append(str(v))
    skills = resume_parsed.get("skills") or {}
    if isinstance(skills, dict):
        for bucket in skills.values():
            if isinstance(bucket, list):
                parts.extend(str(x) for x in bucket if x)
    for exp in resume_parsed.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        for k in ("title", "company", "description"):
            v = exp.get(k)
            if v:
                parts.append(str(v))
        for t in exp.get("technologies_used") or []:
            if t:
                parts.append(str(t))
    for proj in resume_parsed.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        for k in ("name", "description", "url"):
            v = proj.get(k)
            if v:
                parts.append(str(v))
        for t in proj.get("technologies") or []:
            if t:
                parts.append(str(t))
    return _norm(" ".join(parts))


def _job_required_skill_set(job: JobListing) -> set[str]:
    raw = job.required_skills
    if isinstance(raw, list):
        return {_norm(x) for x in raw if x}
    if isinstance(raw, dict):
        vals: list[Any] = []
        for v in raw.values():
            if isinstance(v, list):
                vals.extend(v)
            elif v:
                vals.append(v)
        return {_norm(x) for x in vals if x}
    return set()


def _job_description_tokens(description: str) -> set[str]:
    desc = description.lower()
    tokens = set(re.findall(r"[a-z][a-z0-9+#.]{1,24}", desc))
    return {t for t in tokens if len(t) >= 2}


def _skills_to_check_against_resume(job: JobListing) -> list[str]:
    """Ordered list of job skills / keywords to require in the resume."""
    required = _job_required_skill_set(job)
    if required:
        return sorted(required)
    # No structured skills: use longer description tokens as soft requirements
    toks = {t for t in _job_description_tokens(job.description or "") if len(t) >= 4}
    title_toks = set(_job_description_tokens(job.title or ""))
    merged = sorted(toks | title_toks)
    return merged[:20] if merged else []


def _skill_mentioned_in_resume(skill: str, blob: str, resume_skill_set: set[str]) -> bool:
    if skill in resume_skill_set:
        return True
    if len(skill) >= 2 and skill in blob:
        return True
    return False


def score_skills_vs_job(
    job: JobListing,
    resume_parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    blob = _resume_search_blob(resume_parsed)
    resume_skills = _flatten_resume_skills(resume_parsed)
    to_check = _skills_to_check_against_resume(job)
    red_flags: list[str] = []
    details: list[dict[str, Any]] = []

    if not to_check:
        return {
            "points": 0.0,
            "max": _SKILLS_MAX,
            "red_flags": ["Job has no required_skills or extractable keywords in the description."],
            "details": [],
            "skills_evaluated": [],
        }

    matched = 0
    for sk in to_check:
        ok = _skill_mentioned_in_resume(sk, blob, resume_skills)
        if ok:
            matched += 1
        else:
            red_flags.append(f"Job expects '{sk}' but it was not found clearly on the resume.")
        details.append({"skill": sk, "found_on_resume": ok})

    ratio = matched / len(to_check)
    points = round(ratio * _SKILLS_MAX, 2)
    return {
        "points": min(_SKILLS_MAX, points),
        "max": _SKILLS_MAX,
        "red_flags": red_flags,
        "details": details,
        "skills_evaluated": to_check,
    }


def _job_experience_band_years(level: str) -> tuple[float, float]:
    """Rough (min, max) years suitable for the job's experience_level string."""
    l = (level or "").lower()
    if any(x in l for x in ("entry", "junior", "intern", "graduate")):
        return 0.0, 2.5
    if any(x in l for x in ("mid", "intermediate", "ii", "2-5")):
        return 2.0, 6.0
    if "senior" in l or "sr." in l or "sr " in l:
        return 5.0, 25.0
    if any(x in l for x in ("lead", "principal", "staff", "architect", "manager")):
        return 7.0, 40.0
    return 1.0, 10.0


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _earliest_job_year(resume_parsed: dict[str, Any] | None) -> int | None:
    if not resume_parsed:
        return None
    years: list[int] = []
    for exp in resume_parsed.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        for field in (exp.get("start_date"), exp.get("end_date")):
            if not field:
                continue
            for m in _YEAR_RE.finditer(str(field)):
                y = int(m.group(0))
                if 1980 <= y <= 2035:
                    years.append(y)
    return min(years) if years else None


def _implied_span_years(earliest_year: int | None) -> float | None:
    if earliest_year is None:
        return None
    return max(0.0, float(datetime.now().year - earliest_year))


def score_experience_vs_job(
    job: JobListing,
    resume_parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    red_flags: list[str] = []
    lo, hi = _job_experience_band_years(job.experience_level)

    resume_years: float | None = None
    if resume_parsed:
        y = resume_parsed.get("years_of_experience")
        try:
            if y is not None:
                resume_years = float(y)
        except (TypeError, ValueError):
            resume_years = None

    span = _implied_span_years(_earliest_job_year(resume_parsed))
    candidates = [x for x in (resume_years, span) if x is not None]
    metric = max(candidates) if candidates else None

    labels: dict[str, Any] = {
        "job_experience_level": job.experience_level,
        "job_implied_years_band": [lo, hi],
        "resume_claimed_years": resume_years,
        "resume_job_span_years": round(span, 2) if span is not None else None,
        "metric_used": round(metric, 2) if metric is not None else None,
    }

    if metric is None:
        return {
            "points": 0.0,
            "max": _EXPERIENCE_MAX,
            "red_flags": ["Resume has no years_of_experience or dated job history to compare."],
            "alignment": "insufficient_data",
            "signals": labels,
        }

    if lo <= metric <= hi:
        pts = float(_EXPERIENCE_MAX)
        alignment = "aligned"
    elif metric < lo:
        gap = lo - metric
        if gap <= 1.5:
            pts = 4.0
            alignment = "slightly_below"
            red_flags.append("Experience is slightly below the typical range for this job level.")
        else:
            pts = 0.0
            alignment = "below_role"
            red_flags.append(
                f"Resume experience (~{metric:.1f} y) looks below this role's typical band ({lo:.0f}–{hi:.0f} y)."
            )
    else:
        gap = metric - hi
        if gap <= 2.0:
            pts = 6.0
            alignment = "slightly_above"
        else:
            pts = 4.0
            alignment = "above_role"
            red_flags.append(
                f"Resume shows substantially more tenure (~{metric:.1f} y) than the posting band ({lo:.0f}–{hi:.0f} y)."
            )

    return {
        "points": pts,
        "max": _EXPERIENCE_MAX,
        "red_flags": red_flags,
        "alignment": alignment,
        "signals": labels,
    }


def compute_resume_reality_match(
    job: JobListing,
    resume_parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    skills_block = score_skills_vs_job(job, resume_parsed)
    exp_block = score_experience_vs_job(job, resume_parsed)

    total = float(skills_block["points"]) + float(exp_block["points"])
    all_flags = list(skills_block.get("red_flags") or []) + list(exp_block.get("red_flags") or [])

    return {
        "total_points": round(total, 2),
        "max_points": _TOTAL_MAX,
        "skills_vs_job": skills_block,
        "experience_vs_job": exp_block,
        "job_context": {
            "job_id": job.id,
            "title": job.title,
            "experience_level": job.experience_level,
        },
        "red_flags": all_flags,
    }
