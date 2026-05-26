"""Database engine factory — Supabase / PostgreSQL only (no local fallback)."""
from __future__ import annotations

import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def normalize_database_url(url: str) -> str:
    """Accept postgresql:// or postgres:// and force asyncpg driver."""
    url = url.strip()
    if not url:
        raise ValueError("DATABASE_URL is empty. Set it in the project root .env file.")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def _needs_ssl(url: str) -> bool:
    lower = url.lower()
    return (
        "supabase" in lower
        or "sslmode=require" in lower
        or "ssl=require" in lower
        or "ssl=true" in lower
    )


def _strip_ssl_query_params(url: str) -> str:
    """asyncpg uses connect_args for SSL; strip ssl=* from the URL query string."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in ("ssl", "sslmode")]
    new_query = urlencode(kept)
    return urlunparse(parsed._replace(query=new_query))


def build_connect_args(url: str, *, ssl_verify: bool = True) -> dict:
    if not _needs_ssl(url):
        return {}
    if ssl_verify:
        try:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return {"ssl": ctx}


def create_database_engine(url: str, *, ssl_verify: bool = True) -> AsyncEngine:
    normalized = _strip_ssl_query_params(normalize_database_url(url))
    return create_async_engine(
        normalized,
        echo=False,
        pool_size=10,
        max_overflow=20,
        connect_args=build_connect_args(normalized, ssl_verify=ssl_verify),
    )


def database_host_from_url(url: str) -> str:
    return urlparse(normalize_database_url(url)).hostname or "unknown"


async def verify_database_connection(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
