from __future__ import annotations

from collections.abc import Awaitable, Callable

import redis.asyncio as redis
from pydantic import BaseModel


async def get_redis_connection(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


async def publish(r: redis.Redis, topic: str, payload: BaseModel) -> None:
    await r.publish(topic, payload.model_dump_json())


async def subscribe_and_handle(
    r: redis.Redis,
    topic: str,
    handler: Callable[[str], Awaitable[None]],
) -> None:
    pubsub = r.pubsub()
    await pubsub.subscribe(topic)
    async for message in pubsub.listen():
        if message["type"] == "message":
            await handler(message["data"])

