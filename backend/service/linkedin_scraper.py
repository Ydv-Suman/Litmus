from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
from time import sleep, monotonic
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from groq import Groq
except ImportError:  # pragma: no cover - depends on deployment environment
    Groq = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on deployment environment
    load_dotenv = None

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_MOCK_LINKEDIN_PROFILES_PATH = Path(__file__).resolve().parent / "mock_linkedin_profiles.json"


def _load_local_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


if load_dotenv is not None:
    load_dotenv(_ENV_PATH)
else:
    _load_local_env_file(_ENV_PATH)


logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
REQUEST_TIMEOUT_SECONDS = 15
OUTX_API_BASE = "https://api.outx.ai"
OUTX_POLL_INTERVAL_SECONDS = 5
OUTX_POLL_TIMEOUT_SECONDS = 90
LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MONTH_LOOKUP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

SENIORITY_PATTERNS = [
    (r"\b(intern|trainee|apprentice)\b", 0),
    (r"\b(junior|jr\.?|entry[- ]level|associate)\b", 1),
    (r"\b(engineer|developer|analyst|consultant|specialist|designer)\b", 2),
    (r"\b(ii|mid|intermediate)\b", 3),
    (r"\b(senior|sr\.?|lead)\b", 4),
    (r"\b(staff|principal|architect|manager|head)\b", 5),
    (r"\b(director|vice president|vp|chief|cto|ceo|coo|cpo)\b", 6),
]


class LinkedInAnalyserError(RuntimeError):
    pass


@dataclass
class LinkedInExperience:
    title: str
    company: str
    start_date: str
    end_date: str
    duration_months: int


def score_linkedin_credibility(
    linkedin_url: str,
    resume_data: Optional[dict[str, Any]] = None,
    job: Optional[Any] = None,
) -> float:
    analysis = analyze_linkedin_profile(
        linkedin_url=linkedin_url,
        resume_data=resume_data,
        job=job,
    )
    return analysis["score"]


def analyze_linkedin_profile(
    linkedin_url: str,
    resume_data: Optional[dict[str, Any]] = None,
    job: Optional[Any] = None,
) -> dict[str, Any]:
    normalized_url = _normalize_linkedin_url(linkedin_url)
    mock_profile = _mock_profile_for_url(normalized_url)
    if mock_profile is not None:
        result = _build_analysis_result(
            linkedin_url=normalized_url,
            merged_profile=mock_profile,
            resume_data=resume_data,
            job=job,
        )
        result["data_source"] = "mock"
        return result

    try:
        outx_profile = _fetch_profile_via_outx(normalized_url)
        public_profile = _profile_from_outx(normalized_url, outx_profile)
    except LinkedInAnalyserError as exc:
        fallback_profile = _fallback_profile_from_resume(
            linkedin_url=normalized_url,
            resume_data=resume_data,
            blocked_reason=str(exc),
        )
        return _build_analysis_result(
            linkedin_url=normalized_url,
            merged_profile=fallback_profile,
            resume_data=resume_data,
            job=job,
        )

    groq_profile = _extract_profile_with_groq(
        linkedin_url=normalized_url,
        public_profile=public_profile,
        resume_data=resume_data,
        job=job,
    )
    merged_profile = _merge_profile_data(public_profile, groq_profile)

    return _build_analysis_result(
        linkedin_url=normalized_url,
        merged_profile=merged_profile,
        resume_data=resume_data,
        job=job,
    )


def _build_analysis_result(
    linkedin_url: str,
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> dict[str, Any]:
    role_score, role_reason = _score_role_and_tenure(
        merged_profile=merged_profile,
        resume_data=resume_data,
        job=job,
    )
    endorsements_score, endorsements_reason = _score_skill_endorsements(
        merged_profile=merged_profile,
        resume_data=resume_data,
        job=job,
    )
    trajectory_score, trajectory_reason = _score_career_trajectory(
        merged_profile=merged_profile,
        resume_data=resume_data,
        job=job,
    )

    total_points = role_score + endorsements_score + trajectory_score

    return {
        "linkedin_url": linkedin_url,
        "score": round(total_points / 30.0, 4),
        "points": round(total_points, 2),
        "max_points": 30,
        "criteria": {
            "role_tenure_match": {
                "score": round(role_score, 2),
                "max": 12,
                "reason": role_reason,
            },
            "skill_endorsements": {
                "score": round(endorsements_score, 2),
                "max": 8,
                "reason": endorsements_reason,
            },
            "career_trajectory": {
                "score": round(trajectory_score, 2),
                "max": 10,
                "reason": trajectory_reason,
            },
        },
        "signals": {
            "fetch_status": merged_profile.get("fetch_status"),
            "headline": merged_profile.get("headline", ""),
            "current_title": merged_profile.get("current_title", ""),
            "experience_count": len(merged_profile.get("experiences", [])),
            "average_tenure_months": _average_tenure_months(merged_profile.get("experiences", [])),
            "relevant_endorsements": _relevant_endorsement_total(
                merged_profile=merged_profile,
                resume_data=resume_data,
                job=job,
            ),
            "relevant_skills_with_endorsements": _relevant_endorsed_skills(
                merged_profile=merged_profile,
                resume_data=resume_data,
                job=job,
            ),
            "data_sources": merged_profile.get("data_sources", []),
        },
        "profile_excerpt": {
            "headline": merged_profile.get("headline", ""),
            "current_title": merged_profile.get("current_title", ""),
            "skills": merged_profile.get("skills", [])[:10],
            "experiences": merged_profile.get("experiences", [])[:5],
        },
    }


def _fallback_profile_from_resume(
    linkedin_url: str,
    resume_data: Optional[dict[str, Any]],
    blocked_reason: str,
) -> dict[str, Any]:
    if not resume_data:
        return {
            "linkedin_url": linkedin_url,
            "fetch_status": "blocked",
            "data_sources": [],
            "headline": "",
            "current_title": "",
            "skills": [],
            "experiences": [],
            "blocked_reason": blocked_reason,
        }

    resume_skills = []
    skills_section = resume_data.get("skills") or {}
    if isinstance(skills_section, dict):
        seen: set[str] = set()
        for bucket in skills_section.values():
            if not isinstance(bucket, list):
                continue
            for item in bucket:
                normalized = _normalize_skill(item)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    resume_skills.append({"name": normalized, "endorsements": 0})

    experiences = []
    for item in resume_data.get("experience") or []:
        if not isinstance(item, dict):
            continue
        experiences.append(
            {
                "title": _clean_whitespace(str(item.get("title", ""))),
                "company": _clean_whitespace(str(item.get("company", ""))),
                "start_date": _clean_whitespace(str(item.get("start_date", ""))),
                "end_date": _clean_whitespace(str(item.get("end_date", ""))),
                "duration_months": _coerce_non_negative_int(item.get("duration_months", 0)),
            }
        )

    headline_parts = [
        _clean_whitespace(str(resume_data.get("current_title", ""))),
        _clean_whitespace(str(resume_data.get("summary", ""))),
    ]
    headline = " | ".join(part for part in headline_parts if part)[:240]

    return {
        "linkedin_url": linkedin_url,
        "fetch_status": "blocked_resume_fallback" if experiences or resume_skills else "blocked",
        "data_sources": ["resume_fallback"] if experiences or resume_skills else [],
        "headline": headline,
        "current_title": _clean_whitespace(str(resume_data.get("current_title", ""))),
        "skills": resume_skills,
        "experiences": experiences,
        "blocked_reason": blocked_reason,
    }


def _mock_profile_for_url(linkedin_url: str) -> Optional[dict[str, Any]]:
    profiles = _load_mock_linkedin_profiles()
    if not profiles:
        return None

    slug = _linkedin_profile_slug(linkedin_url)
    profile = profiles.get(slug)
    if not isinstance(profile, dict):
        return None

    return _profile_from_mock_record(linkedin_url, profile)


def _load_mock_linkedin_profiles() -> dict[str, Any]:
    if not _MOCK_LINKEDIN_PROFILES_PATH.exists():
        return {}
    try:
        raw = _MOCK_LINKEDIN_PROFILES_PATH.read_text()
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load mock LinkedIn profiles: %s", exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _profile_from_mock_record(linkedin_url: str, record: dict[str, Any]) -> dict[str, Any]:
    skills = _normalize_skill_entries(record.get("skills") or [])
    experiences = [
        _normalize_experience_entry(item)
        for item in record.get("experiences") or []
        if isinstance(item, dict)
    ]
    return {
        "linkedin_url": linkedin_url,
        "fetch_status": "mock_profile",
        "data_sources": ["mock_profile_file"],
        "headline": _clean_whitespace(str(record.get("headline", ""))),
        "current_title": _clean_whitespace(str(record.get("current_title", ""))),
        "skills": skills,
        "experiences": experiences,
        "full_name": _clean_whitespace(str(record.get("full_name", ""))),
        "location": _clean_whitespace(str(record.get("location", ""))),
    }


def _normalize_linkedin_url(linkedin_url: str) -> str:
    raw_url = linkedin_url.strip()
    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    if parsed.netloc not in {"linkedin.com", "www.linkedin.com"}:
        raise LinkedInAnalyserError("Only LinkedIn profile URLs are supported.")
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0] not in {"in", "pub"}:
        raise LinkedInAnalyserError("LinkedIn URL must point to a public profile.")
    return f"https://www.linkedin.com/{path_parts[0]}/{path_parts[1]}"


def _fetch_profile_via_outx(linkedin_url: str) -> dict[str, Any]:
    api_key = os.getenv("OUTX_API_KEY", "").strip()
    if not api_key:
        raise LinkedInAnalyserError("OUTX_API_KEY is not configured.")

    profile_slug = _linkedin_profile_slug(linkedin_url)
    task_response = _outx_request_json(
        method="POST",
        path="/linkedin-agent/fetch-profile",
        api_key=api_key,
        payload={"profile_slug": profile_slug},
    )
    task_id = str(task_response.get("api_agent_task_id", "")).strip()
    if not task_id:
        raise LinkedInAnalyserError("OutX did not return an async task ID.")

    deadline = monotonic() + OUTX_POLL_TIMEOUT_SECONDS
    last_status = "pending"
    while monotonic() < deadline:
        status_response = _outx_request_json(
            method="GET",
            path="/linkedin-agent/get-task-status",
            api_key=api_key,
            query={"api_agent_task_id": task_id},
        )
        status_data = status_response.get("data") or {}
        status = str(status_data.get("status", "")).strip().lower()
        if status:
            last_status = status

        if status == "completed":
            task_output = status_data.get("task_output") or {}
            profile = task_output.get("profile") or {}
            if not isinstance(profile, dict) or not profile:
                raise LinkedInAnalyserError("OutX completed without profile data.")
            return profile

        if status in {"failed", "error", "cancelled"}:
            raise LinkedInAnalyserError(f"OutX task ended with status `{status}`.")

        sleep(OUTX_POLL_INTERVAL_SECONDS)

    raise LinkedInAnalyserError(f"OutX task timed out while waiting for profile data (last status: {last_status}).")


def _outx_request_json(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[dict[str, Any]] = None,
    query: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    url = f"{OUTX_API_BASE}{path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"

    request_data = None
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
    }
    if payload is not None:
        request_data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, headers=headers, data=request_data, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
            return json.loads(raw_body) if raw_body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("OutX API request failed for %s: %s", url, body)
        raise LinkedInAnalyserError(_outx_error_message(exc.code, body)) from exc
    except URLError as exc:
        raise LinkedInAnalyserError("OutX API request failed.") from exc


def _outx_error_message(status_code: int, body: str) -> str:
    lowered = body.lower()
    if status_code == 401:
        return "OutX API key is missing or invalid."
    if status_code == 403 and "plugin installation required" in lowered:
        return "OutX requires an active Chrome extension session on a team member browser."
    if status_code == 403:
        return "OutX request was forbidden."
    if status_code == 400 and "profile_slug" in lowered:
        return "OutX rejected the LinkedIn profile slug."
    return f"OutX API request failed: {status_code}"


def _linkedin_profile_slug(linkedin_url: str) -> str:
    parsed = urlparse(linkedin_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise LinkedInAnalyserError("LinkedIn URL must point to a public profile slug.")
    return path_parts[1]


def _profile_from_outx(linkedin_url: str, outx_profile: dict[str, Any]) -> dict[str, Any]:
    positions = outx_profile.get("positions") or []
    normalized_positions = [
        _normalize_outx_position(position)
        for position in positions
        if isinstance(position, dict)
    ]
    current_title = ""
    current_position = next(
        (position for position in normalized_positions if position.get("is_current")),
        normalized_positions[0] if normalized_positions else None,
    )
    if current_position:
        current_title = current_position.get("title", "")

    return {
        "linkedin_url": linkedin_url,
        "fetch_status": "outx",
        "data_sources": ["outx"],
        "headline": _clean_whitespace(str(outx_profile.get("headline", ""))),
        "page_title": "",
        "current_title": current_title or _clean_whitespace(str(outx_profile.get("headline", ""))),
        "skills": [],
        "experiences": [_experience_from_outx_position(position) for position in normalized_positions],
        "about": "",
        "visible_text": "",
        "full_name": _clean_whitespace(str(outx_profile.get("full_name", ""))),
        "location": _clean_whitespace(str(outx_profile.get("location", ""))),
        "profile_slug": _clean_whitespace(str(outx_profile.get("profile_slug", ""))),
        "profile_urn": _clean_whitespace(str(outx_profile.get("profile_urn", ""))),
    }


def _normalize_outx_position(position: dict[str, Any]) -> dict[str, Any]:
    start_year = _coerce_non_negative_int(position.get("start_year"))
    start_month = _coerce_month(position.get("start_month"))
    end_year = _coerce_non_negative_int(position.get("end_year"))
    end_month = _coerce_month(position.get("end_month"))
    is_current = bool(position.get("is_current"))

    duration_months = 0
    if start_year:
        end_date = date.today() if is_current or not end_year else date(end_year, end_month or 1, 1)
        start_date = date(start_year, start_month or 1, 1)
        duration_months = _month_delta(start_date, end_date)

    return {
        "title": _clean_whitespace(str(position.get("title", ""))),
        "company_name": _clean_whitespace(str(position.get("company_name", ""))),
        "location": _clean_whitespace(str(position.get("location", ""))),
        "start_year": start_year,
        "start_month": start_month,
        "end_year": end_year,
        "end_month": end_month,
        "is_current": is_current,
        "duration_months": duration_months,
    }


def _experience_from_outx_position(position: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": position.get("title", ""),
        "company": position.get("company_name", ""),
        "start_date": _format_position_date(position.get("start_year", 0), position.get("start_month", 0)),
        "end_date": "Present" if position.get("is_current") else _format_position_date(position.get("end_year", 0), position.get("end_month", 0)),
        "duration_months": position.get("duration_months", 0),
        "is_current": position.get("is_current", False),
    }


def _format_position_date(year: int, month: int) -> str:
    if not year:
        return ""
    if 1 <= month <= 12:
        month_name = datetime(year, month, 1).strftime("%b")
        return f"{month_name} {year}"
    return str(year)


def _coerce_month(value: Any) -> int:
    try:
        month = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return month if 1 <= month <= 12 else 0


def _fetch_public_profile_html(linkedin_url: str) -> str:
    request = Request(linkedin_url, headers=LINKEDIN_HEADERS, method="GET")
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise LinkedInAnalyserError(f"LinkedIn public profile request failed: {exc.code}") from exc
    except URLError as exc:
        raise LinkedInAnalyserError("LinkedIn public profile request failed.") from exc


def _parse_public_profile_html(linkedin_url: str, html: str) -> dict[str, Any]:
    json_ld_objects = _extract_json_ld_objects(html)
    person_object = next(
        (
            obj
            for obj in json_ld_objects
            if isinstance(obj, dict) and str(obj.get("@type", "")).lower() == "person"
        ),
        {},
    )

    headline = _extract_meta_content(html, "og:description")
    page_title = _clean_whitespace(_strip_html_tags(_extract_between(html, "<title>", "</title>")))
    current_title = _extract_current_title(person_object, page_title, headline)
    visible_text = _visible_text_from_html(html)

    return {
        "linkedin_url": linkedin_url,
        "fetch_status": "public_html",
        "data_sources": ["public_html"],
        "headline": headline,
        "page_title": page_title,
        "current_title": current_title,
        "skills": _extract_skill_endorsements_from_text(visible_text),
        "experiences": [],
        "about": _truncate_text(visible_text, 5000),
        "visible_text": _truncate_text(visible_text, 20000),
    }


def _extract_json_ld_objects(html: str) -> list[Any]:
    matches = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    objects: list[Any] = []
    for match in matches:
        cleaned = unescape(match).strip()
        if not cleaned:
            continue
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            objects.extend(parsed)
        else:
            objects.append(parsed)
    return objects


def _extract_meta_content(html: str, property_name: str) -> str:
    patterns = [
        rf'<meta[^>]+property="{re.escape(property_name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(property_name)}"',
        rf'<meta[^>]+name="{re.escape(property_name)}"[^>]+content="([^"]*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return _clean_whitespace(unescape(match.group(1)))
    return ""


def _extract_between(text: str, start: str, end: str) -> str:
    start_index = text.lower().find(start.lower())
    if start_index == -1:
        return ""
    start_index += len(start)
    end_index = text.lower().find(end.lower(), start_index)
    if end_index == -1:
        return ""
    return text[start_index:end_index]


def _strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _visible_text_from_html(html: str) -> str:
    stripped = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.IGNORECASE)
    stripped = _strip_html_tags(stripped)
    return _clean_whitespace(unescape(stripped))


def _clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate_text(value: str, limit: int) -> str:
    return value[:limit] if value else ""


def _extract_current_title(person_object: dict[str, Any], page_title: str, headline: str) -> str:
    job_title = person_object.get("jobTitle")
    if isinstance(job_title, str) and job_title.strip():
        return _clean_whitespace(job_title)

    for candidate in (page_title, headline):
        if " - " in candidate:
            parts = [part.strip() for part in candidate.split(" - ") if part.strip()]
            if len(parts) >= 2:
                return parts[1]
    return headline or page_title


def _extract_skill_endorsements_from_text(visible_text: str) -> list[dict[str, Any]]:
    matches = re.findall(
        r"([A-Za-z0-9+#./ -]{2,50})\s+(\d{1,4})\s+endorsements?",
        visible_text,
        flags=re.IGNORECASE,
    )
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_skill, raw_count in matches:
        skill = _normalize_skill(raw_skill)
        if not skill or skill in seen:
            continue
        seen.add(skill)
        skills.append({"name": skill, "endorsements": int(raw_count)})
    return skills


def _extract_profile_with_groq(
    linkedin_url: str,
    public_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> Optional[dict[str, Any]]:
    api_key = _groq_api_key()
    if not api_key or Groq is None:
        return None

    prompt = (
        "Extract structured evidence from a LinkedIn public profile HTML/text capture. "
        "Do not invent facts that are not visible. Return one JSON object only.\n"
        "Schema:\n"
        "{"
        "\"headline\": string, "
        "\"current_title\": string, "
        "\"skills\": [{\"name\": string, \"endorsements\": number}], "
        "\"experiences\": [{\"title\": string, \"company\": string, \"start_date\": string, "
        "\"end_date\": string, \"duration_months\": number}]"
        "}\n"
        "Use 0 endorsements when a skill is visible but no count is shown. "
        "If experience dates are partially visible, infer duration_months conservatively. "
        "If data is absent, return empty arrays or empty strings.\n"
        f"LinkedIn URL: {linkedin_url}\n"
        f"Job title context: {getattr(job, 'title', '')}\n"
        f"Job skills context: {json.dumps(_job_skill_list(job))}\n"
        f"Resume title context: {json.dumps(_resume_title_list(resume_data))}\n"
        f"Public headline: {public_profile.get('headline', '')}\n"
        f"Public title: {public_profile.get('current_title', '')}\n"
        f"Public text: {public_profile.get('visible_text', '')}"
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=_groq_model(),
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are extracting only explicit LinkedIn public-profile evidence. "
                        "Return compact JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return _extract_json_object(content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LinkedIn Groq extraction failed: %s", exc)
        return None


def _merge_profile_data(public_profile: dict[str, Any], groq_profile: Optional[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(public_profile)
    if not groq_profile:
        return merged

    merged["data_sources"] = list(dict.fromkeys(public_profile.get("data_sources", []) + ["groq_structured"]))
    for key in ("headline", "current_title"):
        if groq_profile.get(key):
            merged[key] = str(groq_profile[key]).strip()

    groq_skills = groq_profile.get("skills") or []
    if isinstance(groq_skills, list) and groq_skills:
        merged["skills"] = _normalize_skill_entries(groq_skills)

    groq_experiences = groq_profile.get("experiences") or []
    if isinstance(groq_experiences, list) and groq_experiences:
        merged["experiences"] = [_normalize_experience_entry(item) for item in groq_experiences if isinstance(item, dict)]

    return merged


def _normalize_skill_entries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        name = _normalize_skill(item.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            endorsements = int(item.get("endorsements", 0) or 0)
        except (TypeError, ValueError):
            endorsements = 0
        skills.append({"name": name, "endorsements": max(0, endorsements)})
    return skills


def _normalize_experience_entry(item: dict[str, Any]) -> dict[str, Any]:
    try:
        duration_months = int(item.get("duration_months", 0) or 0)
    except (TypeError, ValueError):
        duration_months = 0
    return {
        "title": _clean_whitespace(str(item.get("title", ""))),
        "company": _clean_whitespace(str(item.get("company", ""))),
        "start_date": _clean_whitespace(str(item.get("start_date", ""))),
        "end_date": _clean_whitespace(str(item.get("end_date", ""))),
        "duration_months": max(0, duration_months),
    }


def _score_role_and_tenure(
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> tuple[float, str]:
    linkedin_titles = _linkedin_title_list(merged_profile)
    resume_titles = _resume_title_list(resume_data)
    job_title = _clean_whitespace(str(getattr(job, "title", "") or ""))

    title_alignment_hits = 0
    if _title_matches_any(merged_profile.get("current_title", ""), resume_titles):
        title_alignment_hits += 1
    if _title_matches_job(merged_profile.get("current_title", ""), job_title):
        title_alignment_hits += 1
    if any(_title_matches_any(title, resume_titles) for title in linkedin_titles[:3]):
        title_alignment_hits += 1

    experiences = merged_profile.get("experiences", [])
    average_tenure = _average_tenure_months(experiences)
    max_gap_months = _largest_gap_months(experiences)
    blocked_reason = merged_profile.get("blocked_reason", "")
    source_prefix = "LinkedIn was blocked, so this uses resume fallback data. " if blocked_reason else ""

    if title_alignment_hits >= 2 and average_tenure >= 24 and max_gap_months <= 6:
        return 12.0, (
            f"{source_prefix}Titles align with the resume/job context and the average tenure is "
            f"{average_tenure:.1f} months."
        )
    if title_alignment_hits >= 1 and average_tenure >= 12:
        score = 5.0
        if average_tenure >= 18:
            score += 2.0
        if max_gap_months <= 6:
            score += 1.0
        return min(8.0, score), (
            f"{source_prefix}Relevant roles are present, but tenure is less stable. Average tenure is "
            f"{average_tenure:.1f} months."
        )
    if linkedin_titles:
        return 3.0, f"{source_prefix}Visible role history shows limited alignment or short average tenure."
    return 0.0, blocked_reason or "LinkedIn public profile did not expose enough role history to verify tenure."


def _score_skill_endorsements(
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> tuple[float, str]:
    blocked_reason = merged_profile.get("blocked_reason", "")
    if blocked_reason:
        if merged_profile.get("skills"):
            return 0.0, (
                "LinkedIn was blocked, so endorsements could not be verified. "
                "Resume skills were available, but endorsement counts remain unavailable."
            )
        return 0.0, blocked_reason

    relevant_skills = _relevant_skill_targets(resume_data, job)
    if not relevant_skills:
        return 0.0, "No relevant job or resume skills were available to compare endorsements."

    relevant_endorsed_skills = _relevant_endorsed_skills(merged_profile, resume_data, job)
    total_relevant_endorsements = sum(item["endorsements"] for item in relevant_endorsed_skills)

    if total_relevant_endorsements >= 10:
        return 8.0, (
            f"Found {total_relevant_endorsements} endorsements across directly relevant LinkedIn skills."
        )
    if total_relevant_endorsements >= 5:
        score = min(6.0, 4.0 + (total_relevant_endorsements - 5) * 0.5)
        return score, (
            f"Found {total_relevant_endorsements} endorsements on relevant LinkedIn skills."
        )
    if total_relevant_endorsements > 0:
        score = min(3.0, 1.0 + (total_relevant_endorsements * 0.5))
        return score, (
            f"Only {total_relevant_endorsements} relevant endorsements were visible on the public profile."
        )
    if merged_profile.get("skills"):
        return 0.5, "LinkedIn public profile exposed skills, but not endorsements on relevant ones."
    return 0.0, "LinkedIn public profile did not expose skill endorsements."


def _score_career_trajectory(
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> tuple[float, str]:
    experiences = [_normalize_experience_entry(item) for item in merged_profile.get("experiences", []) if isinstance(item, dict)]
    blocked_reason = merged_profile.get("blocked_reason", "")
    source_prefix = "LinkedIn was blocked, so this uses resume fallback data. " if blocked_reason else ""
    if len(experiences) < 2:
        current_title = merged_profile.get("current_title", "")
        if current_title:
            return 4.0, f"{source_prefix}Current title is available, but not enough dated history to verify trajectory."
        return 0.0, blocked_reason or "LinkedIn public profile did not expose enough dated history to score trajectory."

    ordered = _sort_experiences_oldest_first(experiences)
    seniority_values = [_title_seniority(item.get("title", "")) for item in ordered if item.get("title")]
    if not seniority_values:
        return 3.0, "LinkedIn history is present, but title seniority could not be classified reliably."

    progression = seniority_values[-1] - seniority_values[0]
    downward_steps = sum(
        1 for previous, current in zip(seniority_values, seniority_values[1:]) if current < previous
    )
    relevant_domain_ratio = _relevant_title_ratio(ordered, resume_data, job)

    if progression >= 2 and downward_steps == 0 and relevant_domain_ratio >= 0.5:
        return 10.0, f"{source_prefix}History shows clear upward progression in a relevant domain."
    if progression >= 0 and downward_steps <= 1:
        score = 5.0
        if progression > 0:
            score += 2.0
        if relevant_domain_ratio >= 0.5:
            score += 1.0
        return min(7.0, score), f"{source_prefix}Career path looks steady, with limited but generally consistent progression."
    return 2.0, f"{source_prefix}Career path appears erratic or includes visible backward seniority moves."


def _average_tenure_months(experiences: list[dict[str, Any]]) -> float:
    durations = [
        int(item.get("duration_months", 0) or 0)
        for item in experiences
        if int(item.get("duration_months", 0) or 0) > 0
    ]
    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 1)


def _largest_gap_months(experiences: list[dict[str, Any]]) -> int:
    ordered = _sort_experiences_oldest_first(experiences)
    largest_gap = 0
    previous_end: Optional[date] = None
    for item in ordered:
        start_date = _parse_partial_date(item.get("start_date", ""))
        end_date = _parse_partial_date(item.get("end_date", "")) or date.today()
        if start_date and previous_end and start_date > previous_end:
            gap = _month_delta(previous_end, start_date)
            if gap > largest_gap:
                largest_gap = gap
        previous_end = end_date
    return largest_gap


def _sort_experiences_oldest_first(experiences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        experiences,
        key=lambda item: _parse_partial_date(item.get("start_date", "")) or date.max,
    )


def _parse_partial_date(value: str) -> Optional[date]:
    cleaned = _clean_whitespace(value).lower()
    if not cleaned or cleaned in {"present", "current", "now"}:
        return None

    year_match = re.search(r"(19|20)\d{2}", cleaned)
    if not year_match:
        return None
    year = int(year_match.group(0))

    month = 1
    for month_name, month_value in MONTH_LOOKUP.items():
        if month_name in cleaned:
            month = month_value
            break
    return date(year, month, 1)


def _month_delta(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _title_matches_any(title: str, candidates: list[str]) -> bool:
    normalized_title = _normalize_title(title)
    if not normalized_title:
        return False
    for candidate in candidates:
        normalized_candidate = _normalize_title(candidate)
        if not normalized_candidate:
            continue
        if normalized_title == normalized_candidate:
            return True
        overlap = _token_overlap_ratio(normalized_title, normalized_candidate)
        if overlap >= 0.6:
            return True
    return False


def _title_matches_job(title: str, job_title: str) -> bool:
    if not job_title:
        return False
    return _token_overlap_ratio(_normalize_title(title), _normalize_title(job_title)) >= 0.45


def _normalize_title(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9+# ]+", " ", str(value).lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = {token for token in left.split() if token not in {"at", "the", "and"}}
    right_tokens = {token for token in right.split() if token not in {"at", "the", "and"}}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def _linkedin_title_list(merged_profile: dict[str, Any]) -> list[str]:
    titles = []
    if merged_profile.get("current_title"):
        titles.append(str(merged_profile["current_title"]))
    for item in merged_profile.get("experiences", []):
        title = str(item.get("title", "")).strip()
        if title:
            titles.append(title)
    return titles


def _resume_title_list(resume_data: Optional[dict[str, Any]]) -> list[str]:
    if not resume_data:
        return []
    titles: list[str] = []
    current_title = resume_data.get("current_title")
    if current_title:
        titles.append(str(current_title))
    for experience in resume_data.get("experience") or []:
        if not isinstance(experience, dict):
            continue
        title = experience.get("title")
        if title:
            titles.append(str(title))
    return titles


def _job_skill_list(job: Optional[Any]) -> list[str]:
    if not job:
        return []
    raw = getattr(job, "required_skills", None)
    if isinstance(raw, list):
        return [_normalize_skill(item) for item in raw if _normalize_skill(item)]
    if isinstance(raw, dict):
        output: list[str] = []
        for value in raw.values():
            if isinstance(value, list):
                output.extend(_normalize_skill(item) for item in value if _normalize_skill(item))
            elif _normalize_skill(value):
                output.append(_normalize_skill(value))
        return output
    return []


def _relevant_skill_targets(resume_data: Optional[dict[str, Any]], job: Optional[Any]) -> set[str]:
    relevant = set(_job_skill_list(job))
    if relevant:
        return relevant

    if not resume_data:
        return set()
    skills = resume_data.get("skills") or {}
    if not isinstance(skills, dict):
        return set()

    output: set[str] = set()
    for bucket in skills.values():
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            normalized = _normalize_skill(item)
            if normalized:
                output.add(normalized)
    return output


def _normalize_skill(value: Any) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip().lower())
    aliases = {
        "react.js": "react",
        "next.js": "next.js",
        "nodejs": "node.js",
        "node": "node.js",
        "js": "javascript",
        "ts": "typescript",
        "postgres": "postgresql",
    }
    return aliases.get(cleaned, cleaned)


def _relevant_endorsed_skills(
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> list[dict[str, Any]]:
    relevant_targets = _relevant_skill_targets(resume_data, job)
    relevant_skills: list[dict[str, Any]] = []
    for item in merged_profile.get("skills", []):
        name = _normalize_skill(item.get("name", ""))
        if not name:
            continue
        if name in relevant_targets:
            relevant_skills.append({"name": name, "endorsements": int(item.get("endorsements", 0) or 0)})
    return relevant_skills


def _relevant_endorsement_total(
    merged_profile: dict[str, Any],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> int:
    return sum(item["endorsements"] for item in _relevant_endorsed_skills(merged_profile, resume_data, job))


def _title_seniority(title: str) -> int:
    normalized = _normalize_title(title)
    for pattern, score in SENIORITY_PATTERNS:
        if re.search(pattern, normalized):
            return score
    return 2


def _relevant_title_ratio(
    experiences: list[dict[str, Any]],
    resume_data: Optional[dict[str, Any]],
    job: Optional[Any],
) -> float:
    if not experiences:
        return 0.0
    resume_titles = _resume_title_list(resume_data)
    job_title = _clean_whitespace(str(getattr(job, "title", "") or ""))
    relevant_hits = 0
    for experience in experiences:
        title = experience.get("title", "")
        if _title_matches_any(title, resume_titles) or _title_matches_job(title, job_title):
            relevant_hits += 1
    return relevant_hits / len(experiences)


def _extract_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _groq_api_key() -> str:
    return str(__import__("os").environ.get("GROQ_API_KEY", "")).strip()


def _groq_model() -> str:
    return str(__import__("os").environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)).strip() or DEFAULT_GROQ_MODEL


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
