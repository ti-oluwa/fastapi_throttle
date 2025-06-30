import asyncio
import time
import typing

from traffik.backends.base import ThrottleBackend
from traffik.exceptions import ConfigurationError
from traffik.types import (
    ConnectionIdentifier,
    ConnectionThrottledHandler,
    HTTPConnectionT,
)


class InMemoryBackend(
    ThrottleBackend[
        typing.Optional[
            typing.MutableMapping[
                str,
                typing.MutableMapping[str, int],
            ]
        ],
        HTTPConnectionT,
    ]
):
    """
    In-memory throttle backend for testing or single-process use.
    Not suitable for production or multi-process environments.
    """

    def __init__(
        self,
        prefix: str = "inmemory",
        identifier: typing.Optional[ConnectionIdentifier[HTTPConnectionT]] = None,
        handle_throttled: typing.Optional[
            ConnectionThrottledHandler[HTTPConnectionT]
        ] = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(
            None,
            prefix=prefix,
            identifier=identifier,
            handle_throttled=handle_throttled,
            persistent=persistent,
        )
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        # Recreate store
        self.connection = {}

    async def get_wait_period(
        self,
        key: str,
        limit: int,
        expires_after: int,
    ) -> int:
        connection = self.connection
        if connection is None:
            raise ConfigurationError("In-memory backend is not initialized")

        now = int(time.monotonic() * 1000)
        record = typing.cast(
            typing.Dict[str, int], connection.get(key, {"count": 0, "start": now})
        )
        elapsed = now - record["start"]

        async with self._lock:
            if elapsed > expires_after:
                # Reset window but we still count as 1
                # since the first request after expiration is allowed
                record = {"count": 1, "start": now}
                connection[key] = record
                return 0

            if record["count"] < limit:
                record["count"] += 1
                connection[key] = record
                return 0
        # Throttled: return remaining wait period
        return expires_after - elapsed

    async def reset(self) -> None:
        if self.connection is None:
            return
        async with self._lock:
            self.connection.clear()

    async def close(self) -> None:
        pass
