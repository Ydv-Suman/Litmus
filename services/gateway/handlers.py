from __future__ import annotations

from typing import Any

import httpx


REQUEST_TIMEOUT = 10.0


async def forward_json(
    *,
    client: httpx.AsyncClient,
    method: str,
    base_url: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    response = await client.request(
        method=method,
        url=f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    return response.status_code, response.json()


async def forward_multipart(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    path: str,
    token: str,
    form_data: dict[str, str],
    filename: str,
    content: bytes,
    content_type: str,
) -> tuple[int, dict[str, Any]]:
    response = await client.post(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        data=form_data,
        files={"resume": (filename, content, content_type)},
        timeout=REQUEST_TIMEOUT,
    )
    return response.status_code, response.json()

