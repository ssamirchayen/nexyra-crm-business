"""Shared sliding-window limit, using Redis server time and one atomic script."""

from hashlib import sha256
from uuid import uuid4

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

_CONSUME = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local window = 60000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000))}
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], window)
return {1, 0}
"""


class RedisRateLimiter:
    def __init__(self, url: str, prefix: str = "nexyra:rate-limit") -> None:
        self.client = Redis.from_url(
            url,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry=Retry(NoBackoff(), 0),
            max_connections=32,
        )
        self.prefix = prefix

    def consume(self, key: tuple[str, str, str], limit: int) -> tuple[bool, int]:
        # Neither client addresses nor integration paths appear in Redis keys.
        digest = sha256("\0".join(key).encode()).hexdigest()
        allowed, retry = self.client.eval(
            _CONSUME, 1, f"{self.prefix}:{digest}", limit, uuid4().hex
        )
        return bool(allowed), int(retry)
