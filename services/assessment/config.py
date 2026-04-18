import os
from dataclasses import dataclass


@dataclass
class Config:
    anthropic_api_key: str
    redis_url: str
    jwt_secret: str
    sync_mode: bool
    frontend_url: str

    @classmethod
    def from_env(cls) -> "Config":
        missing: list[str] = []

        def require(key: str) -> str:
            value = os.getenv(key)
            if not value:
                missing.append(key)
            return value or ""

        config = cls(
            anthropic_api_key=require("ANTHROPIC_API_KEY"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            jwt_secret=require("JWT_SECRET"),
            sync_mode=os.getenv("SYNC_MODE", "false").lower() == "true",
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173"),
        )
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        if len(config.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters")
        return config

