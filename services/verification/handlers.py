from __future__ import annotations

import asyncio
from collections import defaultdict
import ipaddress
import socket
from urllib.parse import urlparse

import anthropic
import httpx
import redis.asyncio as redis
from bs4 import BeautifulSoup

from shared.schemas import (
    ClaudeVerificationAnalysis,
    PipelineTopic,
    ResumeParsedEvent,
    VerificationEvidence,
    VerificationResult,
)


USER_AGENT = (
    "Mozilla/5.0 (compatible; LitmusVerificationBot/1.0; +https://litmus.local)"
)
_domain_last_seen: defaultdict[str, float] = defaultdict(float)
PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
]


def validate_external_url(url: str) -> str:
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


async def fetch_url_evidence(
    *,
    http_client: httpx.AsyncClient,
    url: str,
    github_token: str,
) -> VerificationEvidence:
    hostname = urlparse(url).hostname or "unknown"
    elapsed = asyncio.get_running_loop().time() - _domain_last_seen[hostname]
    if elapsed < 1.0:
        await asyncio.sleep(1.0 - elapsed)
    headers = {"User-Agent": USER_AGENT}
    if github_token and hostname == "github.com":
        headers["Authorization"] = f"Bearer {github_token}"
    response = await http_client.get(url, headers=headers, timeout=10.0)
    _domain_last_seen[hostname] = asyncio.get_running_loop().time()
    response.raise_for_status()
    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)[:2000]
    return VerificationEvidence(source=url, summary=text)


async def call_claude(
    *,
    client: anthropic.AsyncAnthropic,
    user_content: str,
) -> ClaudeVerificationAnalysis:
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=(
                "You are a component of the Litmus hiring platform. "
                "Your output will be parsed programmatically. "
                "Respond ONLY with valid JSON matching this schema: "
                '{"confidence_per_skill":{"skill":"verified"},"overall_confidence":0,"flagged_inconsistencies":["string"],"evidence":[{"source":"string","summary":"string"}]}. '
                "Do not include markdown, explanation, or any text outside the JSON."
            ),
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return ClaudeVerificationAnalysis.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"Claude parse error: {type(exc).__name__}") from exc


async def verify_candidate(
    *,
    client: anthropic.AsyncAnthropic,
    http_client: httpx.AsyncClient,
    event: ResumeParsedEvent,
    github_token: str,
) -> VerificationResult:
    evidence: list[VerificationEvidence] = []
    for url in (
        event.parsed_resume.links.github_url,
        event.parsed_resume.links.linkedin_url,
        event.parsed_resume.links.portfolio_url,
    ):
        if not url:
            continue
        try:
            safe_url = validate_external_url(url)
            evidence.append(
                await fetch_url_evidence(
                    http_client=http_client,
                    url=safe_url,
                    github_token=github_token,
                )
            )
        except (httpx.HTTPError, ValueError):
            evidence.append(
                VerificationEvidence(
                    source=url,
                    summary="Unable to retrieve evidence within verification timeout.",
                )
            )

    analysis = await call_claude(
        client=client,
        user_content=(
            "Review the parsed resume and evidence. "
            "Treat scraping as supporting evidence only, never ground truth. "
            "Parsed resume JSON:\n"
            f"{event.parsed_resume.model_dump_json()}\n"
            "Evidence JSON:\n"
            f"{[item.model_dump(mode='json') for item in evidence]}"
        ),
    )
    return VerificationResult(
        candidate_id=event.candidate_id,
        job_id=event.job_id,
        confidence_per_skill=analysis.confidence_per_skill,
        overall_confidence=analysis.overall_confidence,
        flagged_inconsistencies=analysis.flagged_inconsistencies,
        sources_checked=[item.source for item in evidence],
        evidence=analysis.evidence or evidence,
    )


async def publish_verification(
    *,
    redis_client: redis.Redis,
    result: VerificationResult,
) -> None:
    await redis_client.publish(
        PipelineTopic.VERIFICATION_COMPLETE.value,
        result.model_dump_json(),
    )
