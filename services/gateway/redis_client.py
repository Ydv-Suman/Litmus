from __future__ import annotations

import redis.asyncio as redis


async def get_redis_connection(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)

