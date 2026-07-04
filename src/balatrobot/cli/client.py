"""Client for BlindDeck JSON-RPC 2.0 API."""

from dataclasses import dataclass, field
from typing import Any

import httpx


class APIError(Exception):
    """Error returned by the BlindDeck API."""

    def __init__(self, name: str, message: str, code: int):
        self.name = name
        self.message = message
        self.code = code
        super().__init__(f"{name}: {message}")


@dataclass
class BalatroClient:
    """Sync client for BlindDeck API."""

    host: str = "127.0.0.1"
    port: int = 12346
    timeout: float = 30.0
    _request_id: int = field(default=0, init=False, repr=False)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a JSON-RPC 2.0 method and return the result.

        Raises:
            APIError: If the API returns an error response.
            httpx.ConnectError: If connection to server fails.
        """
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._request_id,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.url, json=payload)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            error = data["error"]
            raise APIError(
                name=error["data"]["name"],
                message=error["message"],
                code=error["code"],
            )
        return data["result"]
