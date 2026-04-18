from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import tempfile
from urllib.parse import urlparse

import anthropic
import docx
import fitz
import httpx
import redis.asyncio as redis

from shared.schemas import (
    ClaudeExtractionResult,
    ParsedResume,
    PipelineTopic,
    ResumeParsedEvent,
    ResumeSubmission,
)


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024
PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
]


def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        document = fitz.open(file_path)
        try:
            return "\n".join(page.get_text() for page in document)
        finally:
            document.close()

    document = docx.Document(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def validate_external_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are accepted")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname")
    candidate_addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        candidate_addresses.append(ipaddress.ip_address(hostname))
    except ValueError:
        try:
            for record in socket.getaddrinfo(hostname, None):
                candidate_addresses.append(ipaddress.ip_address(record[4][0]))
        except socket.gaierror as exc:
            raise ValueError("URL hostname could not be resolved") from exc
    for candidate_ip in candidate_addresses:
        for private_range in PRIVATE_RANGES:
            if candidate_ip in private_range:
                raise ValueError("URL resolves to a private address")
    return url


async def validate_and_parse_resume(content: bytes, content_type: str) -> str:
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError("Only PDF and DOCX files are accepted")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File exceeds 10MB limit")

    suffix = ".pdf" if "pdf" in content_type else ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    try:
        return await asyncio.to_thread(extract_text, tmp_path)
    finally:
        os.unlink(tmp_path)


async def call_claude(
    *,
    client: anthropic.AsyncAnthropic,
    user_content: str,
) -> ClaudeExtractionResult:
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=(
                "You are a component of the Litmus hiring platform. "
                "Your output will be parsed programmatically. "
                "Respond ONLY with valid JSON matching this schema: "
                '{"skills":["string"],"experience":[{"title":"string","company":"string","years":1.0,"description":"string"}],"education":[{"institution":"string","degree":"string","year":"string"}],"claimed_seniority":"string"}. '
                "Do not include markdown, explanation, or any text outside the JSON."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return ClaudeExtractionResult.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"Claude parse error: {type(exc).__name__}") from exc


async def build_parsed_resume(
    *,
    client: anthropic.AsyncAnthropic,
    submission: ResumeSubmission,
    resume_text: str,
) -> ParsedResume:
    extraction = await call_claude(
        client=client,
        user_content=(
            "Normalize the following resume into Litmus schema fields.\n"
            f"Candidate name: {submission.name}\n"
            f"Candidate email: {submission.email}\n"
            f"Resume text:\n{resume_text}"
        ),
    )
    return ParsedResume(
        candidate_id=submission.candidate_id,
        job_id=submission.job_id,
        name=submission.name,
        email=submission.email,
        resume_text=resume_text,
        skills=extraction.skills,
        experience=extraction.experience,
        education=extraction.education,
        links=submission.links,
        claimed_seniority=extraction.claimed_seniority,
    )


async def dispatch_resume(
    *,
    config: object,
    redis_client: redis.Redis,
    http_client: httpx.AsyncClient,
    parsed_resume: ParsedResume,
    token: str,
) -> None:
    event = ResumeParsedEvent(candidate_id=parsed_resume.candidate_id, job_id=parsed_resume.job_id, parsed_resume=parsed_resume)
    if getattr(config, "sync_mode"):
        payload = event.model_dump(mode="json")
        headers = {"Authorization": f"Bearer {token}"}
        await asyncio.gather(
            http_client.post(
                f"{getattr(config, 'job_match_service_url')}/internal/job-match/from-resume",
                json=payload,
                headers=headers,
                timeout=10.0,
            ),
            http_client.post(
                f"{getattr(config, 'verification_service_url')}/internal/verification/from-resume",
                json=payload,
                headers=headers,
                timeout=10.0,
            ),
            http_client.post(
                f"{getattr(config, 'fairness_service_url')}/internal/fairness/from-resume",
                json=payload,
                headers=headers,
                timeout=10.0,
            ),
        )
        return

    await redis_client.publish(PipelineTopic.RESUME_PARSED.value, event.model_dump_json())
