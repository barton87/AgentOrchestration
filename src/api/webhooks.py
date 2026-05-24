"""Webhook endpoint registration and delivery helpers."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class WebhookEndpointStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class WebhookDeliveryStatus(str, Enum):
    DELIVERED = "delivered"
    REJECTED = "rejected"
    DISABLED = "disabled"
    RETRYABLE = "retryable"
    FAILED = "failed"


class WebhookValidationError(ValueError):
    """Raised when webhook configuration or delivery input fails closed."""


@dataclass
class WebhookEndpoint:
    """A workspace-scoped outbound webhook endpoint."""

    id: str
    workspace_id: str
    url: str
    secret: str
    events: Set[str] = field(default_factory=set)
    version: int = 1
    status: WebhookEndpointStatus = WebhookEndpointStatus.ACTIVE
    disabled_reason: Optional[str] = None
    delivery_attempts: Dict[str, "WebhookDeliveryResult"] = field(default_factory=dict)


@dataclass(frozen=True)
class WebhookDeliveryResult:
    status: WebhookDeliveryStatus
    status_code: Optional[int] = None
    reason: str = ""


class WebhookRegistry:
    """In-memory registry for workspace-scoped webhook endpoints."""

    def __init__(self):
        self._endpoints: Dict[str, WebhookEndpoint] = {}

    def register(self, endpoint: WebhookEndpoint) -> WebhookEndpoint:
        self._validate_endpoint(endpoint)
        self._endpoints[endpoint.id] = endpoint
        return endpoint

    def get(self, endpoint_id: str, workspace_id: str) -> Optional[WebhookEndpoint]:
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint or endpoint.workspace_id != workspace_id:
            return None
        return endpoint

    def disable(self, endpoint: WebhookEndpoint, reason: str) -> None:
        endpoint.status = WebhookEndpointStatus.DISABLED
        endpoint.version += 1
        endpoint.disabled_reason = reason

    @staticmethod
    def _validate_endpoint(endpoint: WebhookEndpoint) -> None:
        if not endpoint.id:
            raise WebhookValidationError("webhook endpoint id is required")
        if not endpoint.workspace_id:
            raise WebhookValidationError("webhook workspace id is required")
        if not endpoint.secret:
            raise WebhookValidationError("webhook secret is required")
        parsed = urlparse(endpoint.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise WebhookValidationError("webhook endpoint url must be an absolute https URL")


class WebhookDeliveryService:
    """Validate, sign, deliver, and disable webhook endpoints safely."""

    RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self, registry: WebhookRegistry, timeout: float = 10.0):
        self.registry = registry
        self.timeout = timeout

    def deliver(
        self,
        *,
        workspace_id: str,
        endpoint_id: str,
        event_id: str,
        payload: Dict[str, Any],
        event_type: Optional[str] = None,
    ) -> WebhookDeliveryResult:
        if not event_id:
            raise WebhookValidationError("webhook event id is required")

        endpoint = self.registry.get(endpoint_id, workspace_id)
        if endpoint is None:
            return WebhookDeliveryResult(WebhookDeliveryStatus.REJECTED, reason="endpoint not found for workspace")

        previous = endpoint.delivery_attempts.get(event_id)
        if previous:
            return previous

        if endpoint.status == WebhookEndpointStatus.DISABLED:
            result = WebhookDeliveryResult(WebhookDeliveryStatus.DISABLED, reason=endpoint.disabled_reason or "endpoint disabled")
            endpoint.delivery_attempts[event_id] = result
            return result

        if event_type and endpoint.events and event_type not in endpoint.events:
            result = WebhookDeliveryResult(WebhookDeliveryStatus.REJECTED, reason="event type not subscribed for endpoint")
            endpoint.delivery_attempts[event_id] = result
            return result

        public_payload = self._public_payload(payload)
        body = json.dumps(public_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        request = Request(
            endpoint.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-AO-Event-Id": event_id,
                "X-AO-Endpoint-Version": str(endpoint.version),
                "X-AO-Signature": self._signature(endpoint.secret, body),
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = self._result_for_status(response.status, endpoint)
        except HTTPError as error:
            result = self._result_for_status(error.code, endpoint)

        endpoint.delivery_attempts[event_id] = result
        return result

    @staticmethod
    def _public_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if not key.startswith("internal_") and key not in {"workspace_id", "endpoint_id", "secret"}}

    def _result_for_status(self, status_code: int, endpoint: WebhookEndpoint) -> WebhookDeliveryResult:
        if 200 <= status_code < 300:
            return WebhookDeliveryResult(WebhookDeliveryStatus.DELIVERED, status_code=status_code)
        if status_code == 410:
            self.registry.disable(endpoint, "remote endpoint returned 410 Gone")
            return WebhookDeliveryResult(
                WebhookDeliveryStatus.DISABLED,
                status_code=status_code,
                reason="remote endpoint returned 410 Gone",
            )
        if status_code in self.RETRYABLE_STATUS_CODES:
            return WebhookDeliveryResult(WebhookDeliveryStatus.RETRYABLE, status_code=status_code)
        return WebhookDeliveryResult(WebhookDeliveryStatus.FAILED, status_code=status_code)

    @staticmethod
    def _signature(secret: str, body: bytes) -> str:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"


__all__ = [
    "WebhookDeliveryResult",
    "WebhookDeliveryService",
    "WebhookDeliveryStatus",
    "WebhookEndpoint",
    "WebhookEndpointStatus",
    "WebhookRegistry",
    "WebhookValidationError",
]
