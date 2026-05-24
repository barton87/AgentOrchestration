from urllib.error import HTTPError

import pytest

from src.api.webhooks import (
    WebhookDeliveryService,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEndpointStatus,
    WebhookRegistry,
)


def endpoint(endpoint_id="endpoint-1", workspace_id="workspace-a"):
    return WebhookEndpoint(
        id=endpoint_id,
        workspace_id=workspace_id,
        url="https://example.test/webhooks/agent",
        secret="test-secret",
    )


def http_error(status_code):
    return HTTPError(
        url="https://example.test/webhooks/agent",
        code=status_code,
        msg="error",
        hdrs=None,
        fp=None,
    )


def test_register_rejects_non_https_endpoint():
    registry = WebhookRegistry()

    with pytest.raises(ValueError, match="absolute https"):
        registry.register(WebhookEndpoint("endpoint-1", "workspace-a", "http://example.test/hook", "secret"))


def test_delivery_rejects_cross_workspace_endpoint_without_network_call(monkeypatch):
    registry = WebhookRegistry()
    registry.register(endpoint())
    service = WebhookDeliveryService(registry)

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("cross-workspace delivery must fail before urlopen")

    monkeypatch.setattr("src.api.webhooks.urlopen", fail_urlopen)

    result = service.deliver(
        workspace_id="workspace-b",
        endpoint_id="endpoint-1",
        event_id="event-1",
        payload={"ok": True},
    )

    assert result.status == WebhookDeliveryStatus.REJECTED
    assert "workspace" in result.reason


def test_valid_delivery_sends_signed_json_request(monkeypatch):
    registry = WebhookRegistry()
    registry.register(endpoint())
    service = WebhookDeliveryService(registry)
    captured = {}

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = request.data
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("src.api.webhooks.urlopen", fake_urlopen)

    result = service.deliver(
        workspace_id="workspace-a",
        endpoint_id="endpoint-1",
        event_id="event-1",
        payload={"value": 1},
    )

    assert result.status == WebhookDeliveryStatus.DELIVERED
    assert captured["method"] == "POST"
    assert captured["body"] == b'{"value":1}'
    assert captured["headers"]["X-ao-event-id"] == "event-1"
    assert captured["headers"]["X-ao-signature"].startswith("sha256=")


def test_410_gone_disables_endpoint_and_is_idempotent(monkeypatch):
    registry = WebhookRegistry()
    webhook = registry.register(endpoint())
    service = WebhookDeliveryService(registry)
    calls = {"count": 0}

    def gone_once(*args, **kwargs):
        calls["count"] += 1
        raise http_error(410)

    monkeypatch.setattr("src.api.webhooks.urlopen", gone_once)

    first = service.deliver(
        workspace_id="workspace-a",
        endpoint_id="endpoint-1",
        event_id="event-410",
        payload={"value": 1},
    )
    second = service.deliver(
        workspace_id="workspace-a",
        endpoint_id="endpoint-1",
        event_id="event-410",
        payload={"value": 1},
    )

    assert first.status == WebhookDeliveryStatus.DISABLED
    assert first.status_code == 410
    assert second == first
    assert calls["count"] == 1
    assert webhook.status == WebhookEndpointStatus.DISABLED
    assert webhook.disabled_reason == "remote endpoint returned 410 Gone"


def test_retryable_status_does_not_disable_endpoint(monkeypatch):
    registry = WebhookRegistry()
    webhook = registry.register(endpoint())
    service = WebhookDeliveryService(registry)

    monkeypatch.setattr("src.api.webhooks.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(http_error(503)))

    result = service.deliver(
        workspace_id="workspace-a",
        endpoint_id="endpoint-1",
        event_id="event-retry",
        payload={"value": 1},
    )

    assert result.status == WebhookDeliveryStatus.RETRYABLE
    assert result.status_code == 503
    assert webhook.status == WebhookEndpointStatus.ACTIVE
