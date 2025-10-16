"""Simple NATS client wrapper for AgentMesh hackathon."""

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

logger = logging.getLogger(__name__)


class NATSWrapper:
    """Simple NATS client wrapper providing publish, subscribe, and request methods."""

    def __init__(self, url: str = "nats://localhost:4222", timeout: int = 5):
        """Initialize NATS wrapper.

        Args:
            url: NATS server URL (default: nats://localhost:4222)
            timeout: Request timeout in seconds (default: 5)
        """
        self.url = url
        self.timeout = timeout
        self.nc: NATSClient | None = None
        self._subscriptions: list = []

    async def connect(self) -> None:
        """Connect to NATS server."""
        try:
            self.nc = await nats.connect(self.url)
            logger.info(f"Connected to NATS at {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.drain()
            await self.nc.close()
            logger.info("Disconnected from NATS")

    async def publish(self, subject: str, data: dict[str, Any]) -> None:
        """Publish a message to a subject (fire and forget).

        Args:
            subject: NATS subject to publish to
            data: Data dictionary to publish (will be JSON encoded)
        """
        if not self.nc:
            logger.error("Not connected to NATS")
            return

        try:
            payload = json.dumps(data).encode()
            await self.nc.publish(subject, payload)
            logger.debug(f"Published to {subject}: {data}")
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[dict[str, Any]], None]
        | Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
        | Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        """Subscribe to a subject with a callback function.

        Args:
            subject: NATS subject to subscribe to
            callback: Callback function (sync or async) to handle received messages
                     If async callback returns a dict, it will be sent as a reply (request-reply pattern)
        """
        if not self.nc:
            logger.error("Not connected to NATS")
            return

        async def message_handler(msg: Msg) -> None:
            try:
                data = json.loads(msg.data.decode())
                logger.debug(f"Received on {subject}: {data}")

                # Run callback
                if asyncio.iscoroutinefunction(callback):
                    result: dict[str, Any] | None = await callback(data)

                    # If callback returns a result and message has reply subject, send response
                    if result is not None and msg.reply and self.nc:
                        reply_payload = json.dumps(result).encode()
                        await self.nc.publish(msg.reply, reply_payload)
                        logger.debug(f"Sent reply to {msg.reply}: {result}")
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error handling message on {subject}: {e}")

                # Send error response if this is a request-reply
                if msg.reply and self.nc:
                    error_response = {"status": "error", "error": str(e)}
                    await self.nc.publish(
                        msg.reply, json.dumps(error_response).encode()
                    )

        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self._subscriptions.append(sub)
            logger.info(f"Subscribed to {subject}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")

    async def request(
        self, subject: str, data: dict[str, Any], timeout: int | None = None
    ) -> dict[str, Any] | None:
        """Send a request and wait for a response (request-response pattern).

        Args:
            subject: NATS subject to send request to
            data: Data dictionary to send (will be JSON encoded)
            timeout: Optional timeout in seconds (default: use self.timeout)

        Returns:
            Response data dictionary or None if timeout/error
        """
        if not self.nc:
            logger.error("Not connected to NATS")
            return None

        try:
            payload = json.dumps(data).encode()
            timeout_val = timeout if timeout is not None else self.timeout

            response = await self.nc.request(subject, payload, timeout=timeout_val)
            response_data: dict[str, Any] = json.loads(response.data.decode())
            logger.debug(f"Request to {subject} got response: {response_data}")
            return response_data
        except asyncio.TimeoutError:
            logger.error(f"Request to {subject} timed out")
            return None
        except Exception as e:
            logger.error(f"Request to {subject} failed: {e}")
            return None

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self.nc is not None and self.nc.is_connected
