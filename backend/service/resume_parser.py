"""
Extract structured fields from a resume PDF.

Uses pypdf for text extraction. The LLM / structured path requires pypdf
(listed in requirements.txt). The heuristic parse_resume_pdf path can still use
a regex fallback when pypdf is missing.

LLM extraction uses Groq only (official groq Python SDK; pip install groq).
Set GROQ_API_KEY in backend/.env (loaded automatically).
Optional: GROQ_BASE_URL (host only, e.g. https://api.groq.com — do not append /openai/v1; the SDK adds it),
GROQ_MODEL or LLM_MODEL.

Primary API: structure_resume_from_pdf_bytes(pdf_bytes) → structured dict.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

from dotenv import load_dotenv

# Load backend/.env even when the process cwd is not the backend directory (e.g. uvicorn from repo root).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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


def _sanitize_extracted_text(text: str) -> str:
    """Drop PDF/binary control noise; keep normal text and newlines."""
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if ch in "\n\r\t":
            out.append(ch)
        elif o < 32 or o == 0x7F:
            continue
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _is_plausible_resume_text(text: str) -> bool:
    """Reject binary/garbage extraction (e.g. regex fallback on complex PDFs)."""
    if len(text) < 35:
        return False
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0 or letters / len(text) < 0.12:
        return False
    if text.count(" ") + text.count("\n") < 4:
        return False
    return True


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


def _groq_key_and_model() -> tuple[str, str]:
    groq = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq:
        raise ValueError(
            "Resume LLM uses Groq only. Set GROQ_API_KEY in backend/.env "
            "(see load_dotenv in this module)."
        )
    model = (
        os.environ.get("GROQ_MODEL")
        or os.environ.get("LLM_MODEL")
        or "llama-3.3-70b-versatile"
    )
    return groq, model


def _post_chat_completion(prompt: str, *, timeout_s: float = 120.0) -> str:
    """
    Call Groq via the official SDK. Raw urllib triggers Cloudflare 403 / error 1010 for many clients.
    """
    api_key, model = _groq_key_and_model()
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "Install the Groq SDK: pip install groq (listed in backend/requirements.txt)."
        ) from exc

    # Groq() defaults to base_url=https://api.groq.com; the SDK appends /openai/v1/....
    # Passing .../openai/v1 as base_url duplicates the path (404 unknown_url).
    client = Groq(api_key=api_key)
    system_msg = (
        "You reply with a single valid JSON object only. No markdown fences, no commentary."
    )
    user_messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=user_messages,
            temperature=0.2,
            timeout=timeout_s,
            max_completion_tokens=8192,
            response_format={"type": "json_object"},
        )
    except Exception:
        # Some models reject json_object; retry without it.
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=user_messages,
                temperature=0.2,
                timeout=timeout_s,
                max_completion_tokens=8192,
            )
        except Exception as second_exc:
            raise RuntimeError(f"Groq API request failed: {second_exc}") from second_exc

    if not completion.choices:
        raise RuntimeError(f"Groq returned no choices: {completion!r}")
    content = completion.choices[0].message.content
    out = content if content is not None else ""
    if not out.strip():
        raise RuntimeError(
            "Groq returned empty message content. The PDF text may be empty, too long, or blocked; "
            "try another PDF or set GROQ_MODEL to a supported chat model."
        )
    return out


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
    raw = _strip_markdown_json_fence((content or "").strip())
    if not raw:
        raise ValueError("LLM returned empty text; cannot parse JSON.")

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    idx = raw.find("{")
    if idx >= 0:
        try:
            parsed, _ = json.JSONDecoder().raw_decode(raw[idx:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    preview = raw[:400].replace("\n", " ")
    raise ValueError(
        f"LLM did not return parseable JSON. Start of response: {preview!r}"
    )


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


# Groq context limits vary by model; very long prompts can yield empty completions.
_MAX_RESUME_CHARS_FOR_LLM = 24_000


def resume_text_to_structured(resume_text: str) -> dict[str, Any]:
    """
    Call the configured LLM to map plain resume text into the structured schema.
    """
    text = resume_text.strip()
    if not text:
        return _empty_resume_structure()
    text = _sanitize_extracted_text(text)
    if not _is_plausible_resume_text(text):
        raise ValueError(
            "Resume text is not readable enough to parse (too short or looks like corrupted/binary data)."
        )
    if len(text) > _MAX_RESUME_CHARS_FOR_LLM:
        text = text[:_MAX_RESUME_CHARS_FOR_LLM] + "\n\n[... truncated for API length ...]"
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
    raw = _extract_text_pypdf(resume_bytes)
    if raw is None:
        raise ValueError(
            "pypdf is not installed in the Python environment running the API. "
            "Activate your backend venv, then: pip install pypdf "
            "(or: python -m pip install pypdf — must be the same interpreter as uvicorn)."
        )
    resume_text = raw.strip()
    if not resume_text:
        resume_text = _extract_text_fallback(resume_bytes).strip()
    resume_text = _sanitize_extracted_text(resume_text)
    if not _is_plausible_resume_text(resume_text):
        raise ValueError(
            "Could not extract readable text from this PDF. It may be image-only "
            "(scan), encrypted, or use fonts that block extraction. Export as a "
            "text-based PDF or ensure pypdf can read it."
        )
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
