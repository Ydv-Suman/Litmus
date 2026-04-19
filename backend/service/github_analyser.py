import base64
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
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

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")


logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_REPOS_TO_ANALYZE = int(os.getenv("GITHUB_ANALYSER_MAX_REPOS", "6"))
MAX_COMMITS_PAGES = 2
REQUEST_TIMEOUT_SECONDS = 15

FRAMEWORK_PATTERNS: dict[str, tuple[str, ...]] = {
    "python": ("django", "fastapi", "flask", "pydantic", "pytest", "pandas"),
    "javascript": (
        "react",
        "next",
        "express",
        "nestjs",
        "vue",
        "nuxt",
        "svelte",
        "astro",
        "vite",
        "jest",
    ),
    "typescript": (
        "react",
        "next",
        "express",
        "nestjs",
        "vue",
        "nuxt",
        "svelte",
        "astro",
        "vite",
        "jest",
    ),
    "java": ("spring", "spring-boot", "maven", "gradle", "junit"),
    "go": ("gin", "fiber", "echo", "cobra"),
    "rust": ("actix-web", "rocket", "tokio", "axum"),
    "ruby": ("rails", "sinatra", "rspec"),
    "php": ("laravel", "symfony", "phpunit"),
    "c#": (".net", "asp.net", "xunit", "nunit"),
}

TEXT_MANIFESTS = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "go.mod",
    "cargo.toml",
    "gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}

LANGUAGE_KEYWORDS = {
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "ruby",
    "php",
    "c#",
    "c++",
    "c",
    "kotlin",
    "swift",
    "scala",
    "dart",
    "elixir",
}

FRAMEWORK_KEYWORDS = {
    framework
    for frameworks in FRAMEWORK_PATTERNS.values()
    for framework in frameworks
} | {
    "node.js",
    "tailwindcss",
    "tailwind",
    "sqlalchemy",
    "prisma",
    "typeorm",
    "sequelize",
}

SKILL_ALIASES = {
    "js": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "ts": "typescript",
    "golang": "go",
    "py": "python",
    "react.js": "react",
    "next.js": "next",
    "nextjs": "next",
    "vue.js": "vue",
    "nuxt.js": "nuxt",
    "express.js": "express",
    "expressjs": "express",
    "nest.js": "nestjs",
    "nestjs": "nestjs",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "mongodb": "mongodb",
    "mysql": "mysql",
    "redis cache": "redis",
    "aws s3": "aws",
    "amazon web services": "aws",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "k8s": "kubernetes",
    "docker compose": "docker",
    "tailwind css": "tailwindcss",
    "spring boot": "spring-boot",
    "dotnet": ".net",
    ".net core": ".net",
    "asp.net core": "asp.net",
}

DETECTED_SKILL_PATTERNS: dict[str, tuple[str, ...]] = {
    "react": ("react",),
    "next": ("next",),
    "express": ("express",),
    "nestjs": ("nestjs", "@nestjs"),
    "vue": ("vue",),
    "nuxt": ("nuxt",),
    "svelte": ("svelte",),
    "astro": ("astro",),
    "vite": ("vite",),
    "jest": ("jest",),
    "pytest": ("pytest",),
    "sqlalchemy": ("sqlalchemy",),
    "prisma": ("prisma",),
    "sequelize": ("sequelize",),
    "typeorm": ("typeorm",),
    "postgresql": ("postgres", "postgresql", "psycopg2", "pgx"),
    "mongodb": ("mongodb", "mongoose", "pymongo"),
    "mysql": ("mysql", "mysql2", "pymysql"),
    "redis": ("redis", "ioredis"),
    "docker": ("dockerfile", "docker-compose", "docker compose"),
    "kubernetes": ("kubernetes", "k8s", "helm"),
    "terraform": ("terraform", ".tf"),
    "aws": ("boto3", "aws-sdk", "@aws-sdk", "serverless"),
    "google cloud": ("google-cloud", "gcp"),
    "azure": ("azure", "@azure"),
}


class GitHubAnalyserError(RuntimeError):
    pass


@dataclass
class RepoSummary:
    name: str
    html_url: str
    description: str
    primary_language: str
    languages: dict[str, int]
    frameworks: list[str]
    detected_skills: list[str]
    pushed_at: Optional[str]
    stargazers_count: int
    forks_count: int
    has_readme: bool
    readme_length: int
    has_tests: bool
    has_ci: bool
    has_docs: bool
    has_src_layout: bool
    top_level_entries: list[str]
    commit_dates: list[datetime]


def score_github_credibility(
    github_url: str,
    resume_data: Optional[Any] = None,
    required_stack: Optional[Iterable[str]] = None,
) -> float:
    """
    Returns a normalized 0..1 credibility score derived from public GitHub evidence.

    Resume data is optional but recommended. When provided, the scorer compares
    claimed skills from the resume against GitHub evidence.
    """
    analysis = analyze_github_profile(
        github_url=github_url,
        resume_data=resume_data,
        required_stack=required_stack,
    )
    return analysis["score"]


def analyze_github_profile(
    github_url: str,
    resume_data: Optional[Any] = None,
    required_stack: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    if required_stack is None and _looks_like_stack_iterable(resume_data):
        required_stack = resume_data
        resume_data = None

    owner = _extract_owner_from_github_url(github_url)
    try:
        user = _github_get(f"/users/{owner}")
        repos = _fetch_repositories(owner)
    except GitHubAnalyserError as exc:
        if "403" in str(exc):
            return _github_forbidden_analysis(
                owner=owner,
                github_url=github_url,
                resume_data=resume_data,
                reason=str(exc),
            )
        raise

    if not repos:
        return _empty_analysis(owner, "No public repositories found for this GitHub profile.")

    selected_repos = _select_repositories_for_analysis(repos)
    repo_summaries = [_summarize_repository(owner, repo) for repo in selected_repos]
    repo_summaries = [repo for repo in repo_summaries if repo is not None]

    if not repo_summaries:
        return _empty_analysis(owner, "Unable to collect enough repository evidence.")

    normalized_required_stack = _normalize_stack(required_stack or ())
    resume_profile = _extract_resume_profile(resume_data)
    claimed_stack = resume_profile["all_claims"] or normalized_required_stack

    tech_stack_score, tech_stack_reason = _score_tech_stack(
        repo_summaries=repo_summaries,
        claimed_stack=claimed_stack,
        resume_profile=resume_profile,
    )
    activity_score, activity_reason = _score_activity(repo_summaries)
    project_quality_score, project_quality_reason = _score_project_quality(
        owner=owner,
        repo_summaries=repo_summaries,
        claimed_stack=claimed_stack,
    )
    collaboration_score, collaboration_reason = _score_collaboration(owner, repos)

    total_points = (
        tech_stack_score
        + activity_score
        + project_quality_score
        + collaboration_score
    )
    normalized_score = round(total_points / 40.0, 4)

    return {
        "github_url": github_url,
        "owner": owner,
        "name": user.get("name") or owner,
        "score": normalized_score,
        "points": round(total_points, 2),
        "max_points": 40,
        "criteria": {
            "tech_stack_match": {
                "score": round(tech_stack_score, 2),
                "max": 15,
                "reason": tech_stack_reason,
            },
            "code_activity_consistency": {
                "score": round(activity_score, 2),
                "max": 10,
                "reason": activity_reason,
            },
            "project_quality_depth": {
                "score": round(project_quality_score, 2),
                "max": 10,
                "reason": project_quality_reason,
            },
            "collaboration_signals": {
                "score": round(collaboration_score, 2),
                "max": 5,
                "reason": collaboration_reason,
            },
        },
        "signals": {
            "primary_languages": _top_languages(repo_summaries),
            "frameworks": _top_frameworks(repo_summaries),
            "detected_skills": _top_detected_skills(repo_summaries),
            "resume_claimed_skills": sorted(claimed_stack),
            "matched_resume_skills": sorted(claimed_stack & _observed_stack(repo_summaries)),
            "unverified_resume_skills": sorted(claimed_stack - _observed_stack(repo_summaries)),
            "repo_count_considered": len(repo_summaries),
            "recently_active_repositories": sum(
                1 for repo in repo_summaries if _is_within_days(repo.pushed_at, 90)
            ),
        },
    }


def _empty_analysis(owner: str, reason: str) -> dict[str, Any]:
    return {
        "github_url": f"https://github.com/{owner}",
        "owner": owner,
        "name": owner,
        "score": 0.0,
        "points": 0,
        "max_points": 40,
        "criteria": {
            "tech_stack_match": {"score": 0, "max": 15, "reason": reason},
            "code_activity_consistency": {"score": 0, "max": 10, "reason": reason},
            "project_quality_depth": {"score": 0, "max": 10, "reason": reason},
            "collaboration_signals": {"score": 0, "max": 5, "reason": reason},
        },
        "signals": {
            "primary_languages": [],
            "frameworks": [],
            "repo_count_considered": 0,
            "recently_active_repositories": 0,
        },
    }


def _github_forbidden_analysis(
    *,
    owner: str,
    github_url: str,
    resume_data: Optional[Any],
    reason: str,
) -> dict[str, Any]:
    resume_profile = _extract_resume_profile(resume_data)
    claimed_stack = sorted(resume_profile["all_claims"])
    fallback_reason = (
        "GitHub API access is currently forbidden or rate-limited, so repository evidence "
        "could not be collected."
    )
    if reason:
        fallback_reason = f"{fallback_reason} ({reason})"

    return {
        "github_url": github_url,
        "owner": owner,
        "name": owner,
        "score": 0.0,
        "points": 0.0,
        "max_points": 40,
        "criteria": {
            "tech_stack_match": {"score": 0.0, "max": 15, "reason": fallback_reason},
            "code_activity_consistency": {"score": 0.0, "max": 10, "reason": fallback_reason},
            "project_quality_depth": {"score": 0.0, "max": 10, "reason": fallback_reason},
            "collaboration_signals": {"score": 0.0, "max": 5, "reason": fallback_reason},
        },
        "signals": {
            "primary_languages": [],
            "frameworks": [],
            "detected_skills": [],
            "resume_claimed_skills": claimed_stack,
            "matched_resume_skills": [],
            "unverified_resume_skills": claimed_stack,
            "repo_count_considered": 0,
            "recently_active_repositories": 0,
            "fetch_status": "forbidden",
        },
    }


def _github_get(path: str, params: Optional[dict[str, Any]] = None) -> Any:
    token = os.getenv("GITHUB_TOKEN")
    url = path if path.startswith("http") else f"{GITHUB_API_BASE}{path}"
    if params:
        filtered_params = {key: value for key, value in params.items() if value is not None}
        url = f"{url}?{urlencode(filtered_params, doseq=True)}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Litmus-GitHub-Analyser",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
            return json.loads(raw_body) if raw_body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code != 404:
            logger.warning("GitHub API request failed for %s: %s", url, body)
        raise GitHubAnalyserError(f"GitHub API request failed: {exc.code}") from exc
    except URLError as exc:
        logger.warning("GitHub API request failed for %s: %s", url, exc.reason)
        raise GitHubAnalyserError("GitHub API request failed.") from exc


def _groq_chat(prompt: str) -> Optional[dict[str, Any]]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    if Groq is None:
        logger.warning("Groq SDK is not installed; skipping LLM-assisted scoring.")
        return None

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_GROQ_MODEL,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are scoring GitHub repositories for engineering credibility. "
                        "Always return one compact JSON object only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq scoring failed: %s", exc)
        return None

    try:
        content = response.choices[0].message.content
        if not content:
            return None
        return _extract_json_object(content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq response parsing failed: %s", exc)
        return None


def _extract_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _extract_owner_from_github_url(github_url: str) -> str:
    raw_url = github_url.strip()
    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise GitHubAnalyserError("Only GitHub profile or repository URLs are supported.")

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise GitHubAnalyserError("GitHub URL must include a username.")

    return path_parts[0]


def _fetch_repositories(owner: str) -> list[dict[str, Any]]:
    repos = _github_get(
        f"/users/{owner}/repos",
        params={"sort": "updated", "per_page": 100, "type": "owner"},
    )
    return repos if isinstance(repos, list) else []


def _select_repositories_for_analysis(repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    non_forks = [repo for repo in repos if not repo.get("fork")]
    ranked = sorted(
        non_forks or repos,
        key=lambda repo: (
            0 if not repo.get("archived", False) else 1,
            _reverse_timestamp_sort_key(repo.get("pushed_at")),
            -(repo.get("stargazers_count", 0) or 0),
            -(repo.get("forks_count", 0) or 0),
        ),
    )
    return ranked[:MAX_REPOS_TO_ANALYZE]


def _summarize_repository(owner: str, repo: dict[str, Any]) -> Optional[RepoSummary]:
    repo_name = repo.get("name")
    if not repo_name:
        return None

    try:
        languages = _github_get(f"/repos/{owner}/{repo_name}/languages")
    except GitHubAnalyserError:
        languages = {}

    try:
        root_entries = _github_get(f"/repos/{owner}/{repo_name}/contents")
    except GitHubAnalyserError:
        root_entries = []

    top_level_names = [
        str(entry.get("name", ""))
        for entry in root_entries
        if isinstance(entry, dict) and entry.get("name")
    ]
    manifest_texts = _fetch_manifest_texts(owner, repo_name, top_level_names)
    frameworks = _detect_frameworks(
        primary_language=repo.get("language") or "",
        manifest_texts=manifest_texts,
    )
    readme_text = _fetch_readme(owner, repo_name)
    commit_dates = _fetch_recent_commit_dates(owner, repo_name, owner)

    normalized_entries = {name.lower() for name in top_level_names}
    has_tests = any(
        name.startswith(("test", "tests", "__tests__")) or "spec" in name
        for name in normalized_entries
    )
    has_ci = ".github" in normalized_entries or ".circleci" in normalized_entries
    has_docs = "docs" in normalized_entries or "documentation" in normalized_entries
    has_src_layout = any(
        folder in normalized_entries for folder in {"src", "app", "server", "client", "backend"}
    )

    return RepoSummary(
        name=repo_name,
        html_url=repo.get("html_url") or f"https://github.com/{owner}/{repo_name}",
        description=repo.get("description") or "",
        primary_language=repo.get("language") or _largest_language(languages),
        languages=languages if isinstance(languages, dict) else {},
        frameworks=frameworks,
        detected_skills=_detect_additional_skills(
            manifest_texts=manifest_texts,
            top_level_names=top_level_names,
            frameworks=frameworks,
            languages=languages if isinstance(languages, dict) else {},
        ),
        pushed_at=repo.get("pushed_at"),
        stargazers_count=repo.get("stargazers_count", 0) or 0,
        forks_count=repo.get("forks_count", 0) or 0,
        has_readme=bool(readme_text),
        readme_length=len(readme_text),
        has_tests=has_tests,
        has_ci=has_ci,
        has_docs=has_docs,
        has_src_layout=has_src_layout,
        top_level_entries=top_level_names[:20],
        commit_dates=commit_dates,
    )


def _fetch_manifest_texts(owner: str, repo_name: str, top_level_names: list[str]) -> dict[str, str]:
    manifests: dict[str, str] = {}
    for file_name in top_level_names:
        if file_name.lower() not in TEXT_MANIFESTS:
            continue
        decoded_content = _fetch_text_file(owner, repo_name, file_name)
        if decoded_content:
            manifests[file_name.lower()] = decoded_content
    return manifests


def _fetch_text_file(owner: str, repo_name: str, file_path: str) -> str:
    try:
        response = _github_get(f"/repos/{owner}/{repo_name}/contents/{file_path}")
    except GitHubAnalyserError:
        return ""

    content = response.get("content")
    encoding = response.get("encoding")
    if not content or encoding != "base64":
        return ""

    try:
        return base64.b64decode(content).decode("utf-8", errors="replace")[:20000]
    except Exception:  # noqa: BLE001
        return ""


def _fetch_readme(owner: str, repo_name: str) -> str:
    try:
        response = _github_get(f"/repos/{owner}/{repo_name}/readme")
    except GitHubAnalyserError:
        return ""

    content = response.get("content")
    encoding = response.get("encoding")
    if not content or encoding != "base64":
        return ""

    try:
        return base64.b64decode(content).decode("utf-8", errors="replace")[:30000]
    except Exception:  # noqa: BLE001
        return ""


def _fetch_recent_commit_dates(owner: str, repo_name: str, author: str) -> list[datetime]:
    since = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    commit_dates: list[datetime] = []

    for page in range(1, MAX_COMMITS_PAGES + 1):
        try:
            commits = _github_get(
                f"/repos/{owner}/{repo_name}/commits",
                params={
                    "author": author,
                    "since": since,
                    "per_page": 100,
                    "page": page,
                },
            )
        except GitHubAnalyserError:
            break

        if not isinstance(commits, list) or not commits:
            break

        for commit in commits:
            date_value = (
                commit.get("commit", {})
                .get("author", {})
                .get("date")
            )
            parsed_date = _parse_github_datetime(date_value)
            if parsed_date is not None:
                commit_dates.append(parsed_date)

        if len(commits) < 100:
            break

    return commit_dates


def _parse_github_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _reverse_timestamp_sort_key(value: Optional[str]) -> float:
    parsed = _parse_github_datetime(value)
    if parsed is None:
        return float("inf")
    return -parsed.timestamp()


def _detect_frameworks(primary_language: str, manifest_texts: dict[str, str]) -> list[str]:
    discovered: set[str] = set()
    language_key = primary_language.strip().lower()
    patterns = FRAMEWORK_PATTERNS.get(language_key, ())

    for file_name, text in manifest_texts.items():
        lowered = text.lower()
        for pattern in patterns:
            if pattern in lowered:
                discovered.add(pattern)

        if file_name == "package.json":
            try:
                package_data = json.loads(text)
                dependency_names = set(package_data.get("dependencies", {})) | set(
                    package_data.get("devDependencies", {})
                )
                for dependency_name in dependency_names:
                    lowered_name = dependency_name.lower()
                    if lowered_name in FRAMEWORK_PATTERNS["javascript"] or lowered_name in FRAMEWORK_PATTERNS["typescript"]:
                        discovered.add(lowered_name)
            except json.JSONDecodeError:
                continue

    return sorted(discovered)


def _detect_additional_skills(
    manifest_texts: dict[str, str],
    top_level_names: list[str],
    frameworks: list[str],
    languages: dict[str, int],
) -> list[str]:
    haystacks = [text.lower() for text in manifest_texts.values()]
    haystacks.append(" ".join(name.lower() for name in top_level_names))
    joined_text = "\n".join(haystacks)

    detected = {
        _canonicalize_skill(language)
        for language in languages
        if _canonicalize_skill(language)
    }
    detected.update(frameworks)

    for skill, patterns in DETECTED_SKILL_PATTERNS.items():
        if any(pattern in joined_text for pattern in patterns):
            detected.add(skill)

    return sorted(detected)


def _score_tech_stack(
    repo_summaries: list[RepoSummary],
    claimed_stack: set[str],
    resume_profile: dict[str, Any],
) -> tuple[float, str]:
    dominant_language, language_share = _dominant_language(repo_summaries)
    framework_counts = Counter(skill for repo in repo_summaries for skill in repo.detected_skills)
    dominant_framework = framework_counts.most_common(1)[0][0] if framework_counts else ""
    observed_stack = _observed_stack(repo_summaries)

    if claimed_stack:
        matched_tools = len(observed_stack & claimed_stack)
        total_claimed = len(claimed_stack)
        match_ratio = matched_tools / total_claimed if total_claimed else 0.0
        primary_claimed_language = resume_profile["primary_language"]
        primary_claimed_framework = resume_profile["primary_framework"]
        primary_language_match = bool(
            primary_claimed_language and primary_claimed_language == dominant_language
        )
        primary_framework_match = bool(
            primary_claimed_framework and primary_claimed_framework in observed_stack
        )

        if primary_language_match and (not primary_claimed_framework or primary_framework_match):
            score = round(min(15.0, 13.0 + (2.0 * match_ratio)), 2)
            return score, (
                f"Strong resume-to-GitHub stack match. Claimed primary language "
                f"`{primary_claimed_language}` matches observed GitHub work, with "
                f"{matched_tools} of {total_claimed} claimed technologies verified."
            )
        if match_ratio >= 0.35 or primary_language_match or primary_framework_match:
            score = round(min(12.0, 8.0 + (4.0 * match_ratio)), 2)
            return score, (
                f"Partial stack match. Verified {matched_tools} of {total_claimed} claimed "
                f"resume technologies against public repositories."
            )
        score = round(min(4.0, 4.0 * match_ratio), 2)
        return score, "Claimed resume stack differs materially from observable GitHub project work."

    stack_evidence_score = 4.0
    if dominant_language:
        stack_evidence_score += 6.0 * language_share
    if dominant_framework:
        stack_evidence_score += 3.0
    if len(framework_counts) >= 2:
        stack_evidence_score += 2.0

    score = min(15.0, round(stack_evidence_score, 2))
    return score, (
        "No job stack was supplied, so this score uses GitHub-only stack evidence. "
        f"Dominant language is `{dominant_language or 'unknown'}` with "
        f"{round(language_share * 100)}% share across analyzed repositories."
    )


def _score_activity(repo_summaries: list[RepoSummary]) -> tuple[float, str]:
    monthly_counts: dict[str, int] = defaultdict(int)
    latest_commit: Optional[datetime] = None
    total_commits = 0

    for repo in repo_summaries:
        for commit_date in repo.commit_dates:
            month_key = commit_date.strftime("%Y-%m")
            monthly_counts[month_key] += 1
            total_commits += 1
            if latest_commit is None or commit_date > latest_commit:
                latest_commit = commit_date

    if latest_commit is None:
        pushed_dates = [
            _parse_github_datetime(repo.pushed_at)
            for repo in repo_summaries
            if repo.pushed_at
        ]
        latest_push = max((date for date in pushed_dates if date is not None), default=None)
        if latest_push is None:
            return 0.0, "No recent commit evidence was available."
        days_since_latest = (datetime.now(timezone.utc) - latest_push).days
        if days_since_latest > 180:
            return 1.0, "Last public repository activity is over six months old."
        return 4.0, "Repositories were updated recently, but commit cadence data is limited."

    days_since_latest = (datetime.now(timezone.utc) - latest_commit).days
    active_months = len(monthly_counts)
    max_monthly_commits = max(monthly_counts.values(), default=0)
    concentration = max_monthly_commits / total_commits if total_commits else 1.0

    if days_since_latest <= 90 and active_months >= 6 and concentration <= 0.45:
        return 10.0, (
            f"Recent commits in the last {days_since_latest} days with consistent activity "
            f"across {active_months} months."
        )
    if days_since_latest <= 90 and active_months >= 4:
        return 7.0, (
            f"Recently active, but contribution cadence is uneven across the last 12 months "
            f"({active_months} active months)."
        )
    if days_since_latest <= 180:
        return 5.0, (
            f"Activity is present, but sporadic. Latest commit was {days_since_latest} days ago."
        )
    if days_since_latest <= 365:
        return 2.0, f"Latest commit was {days_since_latest} days ago."
    return 0.0, "Last commit is older than 12 months."


def _score_project_quality(
    owner: str,
    repo_summaries: list[RepoSummary],
    claimed_stack: set[str],
) -> tuple[float, str]:
    heuristic_score = _heuristic_project_quality_score(repo_summaries)

    prompt = (
        "Score these repositories on Project Quality & Depth using a 0-10 scale.\n"
        "Rubric:\n"
        "- 10: production-level structure, tests, good docs.\n"
        "- 5-8: decent structure, some documentation.\n"
        "- 0-4: tutorial clones, no tests, messy structure.\n"
        "Only evaluate observable engineering depth. Ignore README bio claims.\n"
        "Return JSON: {\"score\": number, \"reason\": string}.\n"
        f"Claimed stack context: {sorted(claimed_stack) if claimed_stack else 'not supplied'}\n"
        f"Owner: {owner}\n"
        f"Repositories: {json.dumps([_repo_for_llm(repo) for repo in repo_summaries], ensure_ascii=True)}"
    )
    llm_response = _groq_chat(prompt)

    if llm_response:
        try:
            llm_score = float(llm_response["score"])
            llm_score = max(0.0, min(10.0, llm_score))
            blended_score = round((heuristic_score * 0.55) + (llm_score * 0.45), 2)
            return blended_score, str(llm_response.get("reason", "")).strip()
        except (KeyError, TypeError, ValueError):
            logger.warning("Groq returned malformed project-quality score: %s", llm_response)

    return heuristic_score, (
        "Heuristic quality score based on repo structure, README quality, tests, CI, and docs."
    )


def _heuristic_project_quality_score(repo_summaries: list[RepoSummary]) -> float:
    if not repo_summaries:
        return 0.0

    repo_scores: list[float] = []
    for repo in repo_summaries:
        repo_score = 0.0
        if repo.has_readme:
            repo_score += 2.0 if repo.readme_length >= 500 else 1.0
        if repo.has_tests:
            repo_score += 2.5
        if repo.has_ci:
            repo_score += 1.5
        if repo.has_docs:
            repo_score += 1.0
        if repo.has_src_layout:
            repo_score += 1.5
        if len(repo.top_level_entries) >= 4:
            repo_score += 1.0
        if repo.frameworks:
            repo_score += 0.5

        repo_scores.append(min(10.0, repo_score))

    return round(sum(repo_scores) / len(repo_scores), 2)


def _repo_for_llm(repo: RepoSummary) -> dict[str, Any]:
    return {
        "name": repo.name,
        "description": repo.description,
        "url": repo.html_url,
        "primary_language": repo.primary_language,
        "frameworks": repo.frameworks,
        "detected_skills": repo.detected_skills,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "has_readme": repo.has_readme,
        "readme_length": repo.readme_length,
        "has_tests": repo.has_tests,
        "has_ci": repo.has_ci,
        "has_docs": repo.has_docs,
        "has_src_layout": repo.has_src_layout,
        "top_level_entries": repo.top_level_entries,
        "recent_commits_last_year": len(repo.commit_dates),
    }


def _score_collaboration(owner: str, repos: list[dict[str, Any]]) -> tuple[float, str]:
    merged_external_prs = _count_merged_external_prs(owner)
    if merged_external_prs > 0:
        return 5.0, f"Found {merged_external_prs} merged pull requests authored in other repositories."

    total_stars = sum((repo.get("stargazers_count") or 0) for repo in repos if not repo.get("fork"))
    total_forks = sum((repo.get("forks_count") or 0) for repo in repos if not repo.get("fork"))

    if total_stars + total_forks >= 10:
        return 3.0, (
            f"No external merged PRs found, but own repositories have {total_stars} stars "
            f"and {total_forks} forks."
        )
    if total_stars + total_forks >= 1:
        return 2.0, "No external merged PRs found, but there is some public adoption on own repositories."
    return 0.5, "Mostly solo public repositories with no visible external contribution signals."


def _count_merged_external_prs(owner: str) -> int:
    query = f"type:pr author:{owner} is:merged -user:{owner}"
    try:
        response = _github_get("/search/issues", params={"q": query, "per_page": 1})
    except GitHubAnalyserError:
        return 0
    return int(response.get("total_count", 0) or 0)


def _normalize_stack(values: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for value in values:
        cleaned = _canonicalize_skill(value)
        if cleaned:
            normalized.add(cleaned)
    return normalized


def _canonicalize_skill(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    return SKILL_ALIASES.get(cleaned, cleaned)


def _looks_like_stack_iterable(value: Any) -> bool:
    return isinstance(value, (list, tuple, set))


def _extract_resume_profile(resume_data: Optional[Any]) -> dict[str, Any]:
    parsed_resume = _coerce_resume_data(resume_data)
    if not parsed_resume:
        return {
            "all_claims": set(),
            "primary_language": "",
            "primary_framework": "",
        }

    claim_weights: Counter[str] = Counter()
    language_weights: Counter[str] = Counter()
    framework_weights: Counter[str] = Counter()

    skills_section = parsed_resume.get("skills") or {}
    for category, weight in (
        ("languages", 4),
        ("frameworks", 4),
        ("tools", 2),
        ("cloud", 2),
        ("databases", 2),
    ):
        for skill in skills_section.get(category, []) or []:
            _accumulate_claim(
                claim_weights=claim_weights,
                language_weights=language_weights,
                framework_weights=framework_weights,
                skill=skill,
                weight=weight,
            )

    for experience in parsed_resume.get("experience", []) or []:
        for skill in experience.get("technologies_used", []) or []:
            _accumulate_claim(
                claim_weights=claim_weights,
                language_weights=language_weights,
                framework_weights=framework_weights,
                skill=skill,
                weight=3,
            )

    for project in parsed_resume.get("projects", []) or []:
        for skill in project.get("technologies", []) or []:
            _accumulate_claim(
                claim_weights=claim_weights,
                language_weights=language_weights,
                framework_weights=framework_weights,
                skill=skill,
                weight=2,
            )

    return {
        "all_claims": set(claim_weights),
        "primary_language": language_weights.most_common(1)[0][0] if language_weights else "",
        "primary_framework": framework_weights.most_common(1)[0][0] if framework_weights else "",
    }


def _coerce_resume_data(resume_data: Optional[Any]) -> dict[str, Any]:
    if resume_data is None:
        return {}
    if isinstance(resume_data, str):
        try:
            parsed = json.loads(resume_data)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return resume_data if isinstance(resume_data, dict) else {}


def _accumulate_claim(
    claim_weights: Counter[str],
    language_weights: Counter[str],
    framework_weights: Counter[str],
    skill: Any,
    weight: int,
) -> None:
    normalized_skill = _canonicalize_skill(skill)
    if not normalized_skill:
        return

    claim_weights[normalized_skill] += weight
    if normalized_skill in LANGUAGE_KEYWORDS:
        language_weights[normalized_skill] += weight
    if normalized_skill in FRAMEWORK_KEYWORDS:
        framework_weights[normalized_skill] += weight


def _observed_stack(repo_summaries: list[RepoSummary]) -> set[str]:
    observed: set[str] = set()
    for repo in repo_summaries:
        observed.update(_normalize_stack(repo.languages))
        observed.update(_normalize_stack(repo.frameworks))
        observed.update(_normalize_stack(repo.detected_skills))
    return observed


def _dominant_language(repo_summaries: list[RepoSummary]) -> tuple[str, float]:
    language_bytes: Counter[str] = Counter()
    for repo in repo_summaries:
        if repo.languages:
            language_bytes.update({language.lower(): count for language, count in repo.languages.items()})
        elif repo.primary_language:
            language_bytes.update({repo.primary_language.lower(): 1})

    if not language_bytes:
        return "", 0.0

    dominant_language, dominant_bytes = language_bytes.most_common(1)[0]
    total_bytes = sum(language_bytes.values()) or 1
    return dominant_language, dominant_bytes / total_bytes


def _top_languages(repo_summaries: list[RepoSummary], limit: int = 5) -> list[str]:
    language_bytes: Counter[str] = Counter()
    for repo in repo_summaries:
        if repo.languages:
            language_bytes.update({language.lower(): count for language, count in repo.languages.items()})
        elif repo.primary_language:
            language_bytes.update({repo.primary_language.lower(): 1})
    return [language for language, _count in language_bytes.most_common(limit)]


def _top_frameworks(repo_summaries: list[RepoSummary], limit: int = 5) -> list[str]:
    framework_counts = Counter(framework for repo in repo_summaries for framework in repo.frameworks)
    return [framework for framework, _count in framework_counts.most_common(limit)]


def _top_detected_skills(repo_summaries: list[RepoSummary], limit: int = 10) -> list[str]:
    skill_counts = Counter(skill for repo in repo_summaries for skill in repo.detected_skills)
    return [skill for skill, _count in skill_counts.most_common(limit)]


def _largest_language(languages: dict[str, int]) -> str:
    if not languages:
        return ""
    return max(languages.items(), key=lambda item: item[1])[0]


def _is_within_days(timestamp: Optional[str], days: int) -> bool:
    parsed = _parse_github_datetime(timestamp)
    if parsed is None:
        return False
    return (datetime.now(timezone.utc) - parsed).days <= days
