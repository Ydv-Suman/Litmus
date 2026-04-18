"""
Extract structured fields from a resume PDF.

Uses pypdf when installed (recommended: pip install pypdf). Falls back to a
lightweight literal-string scrape from the PDF bytes when pypdf is missing.

LLM structured extraction: set GROQ_API_KEY (Groq OpenAI-compatible API) or
OPENAI_API_KEY. Optional: LLM_BASE_URL, LLM_MODEL (defaults chosen per provider).

Primary API: structure_resume_from_pdf_bytes(pdf_bytes) → structured dict.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

# --- PDF text extraction -------------------------------------------------


def _extract_text_pypdf(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore[import-not-found, no-redef]
        except ImportError:
            return None
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts) if parts else ""


def _unescape_pdf_string(inner: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == "\\" and i + 1 < len(inner):
            n = inner[i + 1]
            if n in "\\()":
                out.append(n)
                i += 2
                continue
            if n == "n":
                out.append("\n")
                i += 2
                continue
            if n == "r":
                out.append("\r")
                i += 2
                continue
            if n == "t":
                out.append("\t")
                i += 2
                continue
            if n.isdigit():
                octal = n
                j = i + 2
                while j < min(i + 4, len(inner)) and inner[j].isdigit():
                    octal += inner[j]
                    j += 1
                try:
                    out.append(chr(int(octal, 8)))
                except ValueError:
                    out.append(n)
                i = j
                continue
            out.append(n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _extract_text_fallback(data: bytes) -> str:
    """Best-effort text when pypdf is not installed (many simple PDFs work)."""
    s = data.decode("latin-1", errors="ignore")
    chunks: list[str] = []
    for m in re.finditer(r"\((?:\\.|[^\\()])*\)", s):
        inner = m.group(0)[1:-1]
        if len(inner) < 2:
            continue
        chunks.append(_unescape_pdf_string(inner))
    return "\n".join(chunks)


def pdf_to_text(data: bytes) -> str:
    text = _extract_text_pypdf(data)
    if text is not None:
        return text
    return _extract_text_fallback(data)


# --- Field extraction ------------------------------------------------------


_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone: optional +country, separators, extensions
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}(?:\s*(?:x|ext\.?)\s*\d+)?",
    re.IGNORECASE,
)

_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:in|pub)/[a-zA-Z0-9\-_%]+/?",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"https?://(?:www\.)?github\.com/[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}/?",
    re.IGNORECASE,
)

_SECTION_SKIP = frozenset(
    {
        "resume",
        "cv",
        "curriculum vitae",
        "summary",
        "objective",
        "profile",
        "experience",
        "work experience",
        "employment",
        "education",
        "skills",
        "technical skills",
        "projects",
        "certifications",
        "references",
    }
)


def _dedupe_preserve(seq: list[str], key=lambda x: x.lower()) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def _normalize_phone(p: str) -> str:
    return re.sub(r"\s+", " ", p.strip())


def _guess_full_name(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name_pattern = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$")

    for ln in lines[:20]:
        low = ln.lower().rstrip(":")
        if low in _SECTION_SKIP:
            continue
        if ln.startswith("http") or "@" in ln:
            continue
        if _EMAIL_RE.search(ln) or _PHONE_RE.search(ln):
            continue
        if name_pattern.match(ln):
            return ln

    for ln in lines[:8]:
        low = ln.lower().rstrip(":")
        if low in _SECTION_SKIP or ln.startswith("http") or "@" in ln:
            continue
        if 3 <= len(ln) <= 80 and not re.search(r"\d{4}", ln):
            return ln
    return None


def _extract_skills_block(text: str) -> list[str]:
    """Pull comma/bullet lists after a 'Skills' heading."""
    lower = text.lower()
    idx = lower.find("skills")
    if idx == -1:
        return []
    chunk = text[idx : idx + 2500]
    lines = chunk.splitlines()
    skills: list[str] = []
    for ln in lines[1:12]:
        s = ln.strip().lstrip("•*-–—\t ").strip()
        if not s or len(s) > 120:
            continue
        low = s.lower()
        if low in _SECTION_SKIP or low.endswith("experience"):
            break
        if "," in s:
            for part in re.split(r"[,;|]", s):
                p = part.strip()
                if 2 <= len(p) <= 60:
                    skills.append(p)
        elif 2 <= len(s) <= 60:
            skills.append(s)
    return _dedupe_preserve(skills)


# --- LLM structured extraction -------------------------------------------


def _empty_resume_structure() -> dict[str, Any]:
    return {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "github_url": "",
        "linkedin_url": "",
        "portfolio_url": "",
        "summary": "",
        "years_of_experience": 0,
        "current_title": "",
        "skills": {
            "languages": [],
            "frameworks": [],
            "tools": [],
            "cloud": [],
            "databases": [],
        },
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
    }


def build_structured_resume_prompt(resume_text: str) -> str:
    return f"""Extract structured data from this resume text.
Return ONLY a valid JSON object with no extra text.

Resume:
{resume_text}

Return this exact structure:
{{
  "name": "",
  "email": "",
  "phone": "",
  "location": "",
  "github_url": "",
  "linkedin_url": "",
  "portfolio_url": "",
  "summary": "",
  "years_of_experience": 0,
  "current_title": "",
  "skills": {{
    "languages": [],
    "frameworks": [],
    "tools": [],
    "cloud": [],
    "databases": []
  }},
  "experience": [
    {{
      "title": "",
      "company": "",
      "start_date": "",
      "end_date": "",
      "duration_months": 0,
      "description": "",
      "technologies_used": []
    }}
  ],
  "education": [
    {{
      "degree": "",
      "field": "",
      "institution": "",
      "graduation_year": ""
    }}
  ],
  "certifications": [],
  "projects": [
    {{
      "name": "",
      "description": "",
      "technologies": [],
      "url": ""
    }}
  ]
}}
"""


def _llm_connection() -> tuple[str, str, str]:
    groq = os.environ.get("GROQ_API_KEY", "").strip()
    if groq:
        base = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
        return groq, base, model
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "LLM resume extraction requires GROQ_API_KEY or OPENAI_API_KEY (or LLM_API_KEY)."
        )
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    return key, base, model


def _post_chat_completion(prompt: str, *, timeout_s: int = 120) -> str:
    api_key, base_url, model = _llm_connection()
    url = f"{base_url}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if "api.openai.com" in base_url:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response shape: {payload!r}") from exc


def _strip_markdown_json_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_llm_json(content: str) -> dict[str, Any]:
    raw = _strip_markdown_json_fence(content)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM returned JSON that is not an object.")
    return parsed


def _coerce_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _coerce_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _coerce_str_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if isinstance(v, list):
        out: list[str] = []
        for item in v:
            s = _coerce_str(item)
            if s:
                out.append(s)
        return out
    return []


def _normalize_structured_resume(data: dict[str, Any]) -> dict[str, Any]:
    base = _empty_resume_structure()
    skills_in = data.get("skills") if isinstance(data.get("skills"), dict) else {}
    skills_out: dict[str, list[str]] = {}
    for key in base["skills"]:
        skills_out[key] = _coerce_str_list(skills_in.get(key))

    experience_out: list[dict[str, Any]] = []
    for row in data.get("experience") or []:
        if not isinstance(row, dict):
            continue
        experience_out.append(
            {
                "title": _coerce_str(row.get("title")),
                "company": _coerce_str(row.get("company")),
                "start_date": _coerce_str(row.get("start_date")),
                "end_date": _coerce_str(row.get("end_date")),
                "duration_months": _coerce_int(row.get("duration_months"), 0),
                "description": _coerce_str(row.get("description")),
                "technologies_used": _coerce_str_list(row.get("technologies_used")),
            }
        )

    education_out: list[dict[str, Any]] = []
    for row in data.get("education") or []:
        if not isinstance(row, dict):
            continue
        education_out.append(
            {
                "degree": _coerce_str(row.get("degree")),
                "field": _coerce_str(row.get("field")),
                "institution": _coerce_str(row.get("institution")),
                "graduation_year": _coerce_str(row.get("graduation_year")),
            }
        )

    projects_out: list[dict[str, Any]] = []
    for row in data.get("projects") or []:
        if not isinstance(row, dict):
            continue
        projects_out.append(
            {
                "name": _coerce_str(row.get("name")),
                "description": _coerce_str(row.get("description")),
                "technologies": _coerce_str_list(row.get("technologies")),
                "url": _coerce_str(row.get("url")),
            }
        )

    certs = data.get("certifications")
    if isinstance(certs, list):
        certifications_out = [_coerce_str(c) for c in certs if _coerce_str(c)]
    else:
        certifications_out = []

    base.update(
        {
            "name": _coerce_str(data.get("name")),
            "email": _coerce_str(data.get("email")),
            "phone": _coerce_str(data.get("phone")),
            "location": _coerce_str(data.get("location")),
            "github_url": _coerce_str(data.get("github_url")),
            "linkedin_url": _coerce_str(data.get("linkedin_url")),
            "portfolio_url": _coerce_str(data.get("portfolio_url")),
            "summary": _coerce_str(data.get("summary")),
            "years_of_experience": _coerce_int(data.get("years_of_experience"), 0),
            "current_title": _coerce_str(data.get("current_title")),
            "skills": skills_out,
            "experience": experience_out,
            "education": education_out,
            "certifications": certifications_out,
            "projects": projects_out,
        }
    )
    return base


def resume_text_to_structured(resume_text: str) -> dict[str, Any]:
    """
    Call the configured LLM to map plain resume text into the structured schema.
    """
    text = resume_text.strip()
    if not text:
        return _empty_resume_structure()
    prompt = build_structured_resume_prompt(text)
    content = _post_chat_completion(prompt)
    print("[resume_parser] LLM raw response:")
    print(content)
    parsed = _parse_llm_json(content)
    normalized = _normalize_structured_resume(parsed)
    print("[resume_parser] Normalized structured resume (JSON):")
    print(json.dumps(normalized, indent=2, ensure_ascii=False))
    return normalized


def structure_resume_from_pdf_bytes(resume_bytes: bytes) -> dict[str, Any]:
    """
    Single entrypoint: PDF bytes → extracted text → LLM → structured JSON
    (name, email, skills, experience, education, projects, etc.).
    """
    resume_text = pdf_to_text(resume_bytes)
    return resume_text_to_structured(resume_text)


def parse_resume_pdf_structured(
    *,
    file_path: str | Path | None = None,
    data: bytes | None = None,
    file: BinaryIO | None = None,
) -> dict[str, Any]:
    """
    Extract text from a PDF resume, then return LLM-structured fields.
    Pass exactly one of file_path=, data=, or file=.
    """
    if sum(x is not None for x in (file_path, data, file)) != 1:
        raise ValueError("Pass exactly one of file_path=, data=, or file=.")

    if file_path is not None:
        raw = Path(file_path).read_bytes()
    elif data is not None:
        raw = data
    else:
        raw = file.read()  # type: ignore[union-attr]

    return structure_resume_from_pdf_bytes(raw)


def parse_resume_pdf(
    *,
    file_path: str | Path | None = None,
    data: bytes | None = None,
    file: BinaryIO | None = None,
) -> dict[str, Any]:
    """
    Read a PDF resume and return fields useful for applications / screening.

    Provide exactly one of: file_path, data (raw bytes), or file (readable binary).

    Returns keys aligned with submission data plus extras:
    - full_name, emails, phones, linkedin_urls, github_urls (lists where multiple)
    - skills, raw_text
    """
    if sum(x is not None for x in (file_path, data, file)) != 1:
        raise ValueError("Pass exactly one of file_path=, data=, or file=.")

    if file_path is not None:
        raw = Path(file_path).read_bytes()
    elif data is not None:
        raw = data
    else:
        raw = file.read()  # type: ignore[union-attr]

    raw_text = pdf_to_text(raw)
    collapsed = " ".join(raw_text.split())

    emails = _dedupe_preserve(_EMAIL_RE.findall(raw_text))
    phones = _dedupe_preserve(
        [_normalize_phone(m) for m in _PHONE_RE.findall(raw_text)],
        key=lambda p: re.sub(r"\D", "", p),
    )
    linkedin_urls = _dedupe_preserve(_LINKEDIN_RE.findall(collapsed))
    github_urls = _dedupe_preserve(_GITHUB_RE.findall(collapsed))
    skills = _extract_skills_block(raw_text)
    full_name = _guess_full_name(raw_text)

    return {
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "linkedin_urls": linkedin_urls,
        "github_urls": github_urls,
        "skills": skills,
        "raw_text": raw_text.strip(),
    }
