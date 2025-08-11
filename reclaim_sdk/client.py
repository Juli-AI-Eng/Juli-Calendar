from pydantic import BaseModel, Field
import os
import json
from datetime import datetime, timezone
import httpx
from typing import Any, Dict, Optional
from reclaim_sdk.exceptions import (
    ReclaimAPIError,
    RecordNotFound,
    InvalidRecord,
    AuthenticationError,
)


class ReclaimClientConfig(BaseModel):
    token: str = Field(..., description="Reclaim API token")
    base_url: str = Field(
        "https://api.app.reclaim.ai", description="Reclaim API base URL"
    )


class ReclaimClient:
    """
    Thread-safe Reclaim client that creates a new instance per configuration.
    No longer uses singleton pattern to avoid cross-user credential issues.
    """

    def __init__(self, config: ReclaimClientConfig):
        self._config = config
        self._initialize()

    def _initialize(self) -> None:
        # Add a default timeout to prevent hanging requests
        default_timeout = float(os.getenv("RECLAIM_API_TIMEOUT_SECONDS", "60.0"))
        
        self.session = httpx.Client(
            base_url=self._config.base_url,
            headers={"Authorization": f"Bearer {self._config.token}"},
            timeout=default_timeout
        )

    @classmethod
    def configure(cls, token: str, base_url: Optional[str] = None) -> "ReclaimClient":
        """
        Create a new ReclaimClient instance with the given token and optional base URL.
        Each call returns a new, independent client instance.
        """
        config = ReclaimClientConfig(
            token=token,
            base_url=base_url or "https://api.app.reclaim.ai"
        )
        return cls(config)
    
    @classmethod
    def from_env(cls) -> "ReclaimClient":
        """Create a client from environment variables."""
        token = os.environ.get("RECLAIM_TOKEN")
        if not token:
            raise ValueError(
                "Reclaim token is required. Set RECLAIM_TOKEN environment variable or use ReclaimClient.configure()."
            )
        return cls.configure(token=token)

    def request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        if "json" in kwargs:
            kwargs["content"] = json.dumps(
                kwargs.pop("json"), default=self._datetime_encoder
            )
            kwargs["headers"] = kwargs.get("headers", {})
            kwargs["headers"]["Content-Type"] = "application/json"

        try:
            response = self.session.request(method, endpoint, **kwargs)
            response.raise_for_status()
            if (
                method.upper() == "DELETE"
                and response.status_code in (204, 200)
                and not response.content
            ):
                return {}
            return response.json()
        except httpx.HTTPStatusError as e:
            error_data = (
                e.response.json() if e.response.content else {"message": str(e)}
            )
            if e.response.status_code == 401:
                raise AuthenticationError(
                    f"Authentication failed: {error_data.get('message')}"
                )
            elif e.response.status_code == 404:
                raise RecordNotFound(f"Resource not found: {endpoint}")
            elif e.response.status_code in (400, 422):
                raise InvalidRecord(f"Invalid data: {error_data.get('message')}")
            else:
                raise ReclaimAPIError(f"API error: {error_data.get('message')}")
        except httpx.RequestError as e:
            raise ReclaimAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise ReclaimAPIError("Invalid JSON response from API")

    @staticmethod
    def _datetime_encoder(obj: Any) -> str:
        if isinstance(obj, datetime):
            return obj.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        raise TypeError(
            f"Object of type {obj.__class__.__name__} is not JSON serializable"
        )

    def get(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        return self.request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        return self.request("DELETE", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        return self.request("PATCH", endpoint, **kwargs)
