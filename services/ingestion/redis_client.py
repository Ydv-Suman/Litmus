from __future__ import annotations

import redis.asyncio as redis
from pydantic import BaseModel


async def get_redis_connection(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


async def publish(r: redis.Redis, topic: str, payload: BaseModel) -> None:
    await r.publish(topic, payload.model_dump_json())

