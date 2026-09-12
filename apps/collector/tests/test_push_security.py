"""Exercise the real requests redirect machinery without network I/O."""

from types import SimpleNamespace

import pytest
import requests
from orot_core.models import DeviceToken
from orot_core.notifications import SendOutcome
from requests.adapters import BaseAdapter

from orot_collector.push_sender import WebPushSender, _PushSession, _send_push


class RedirectAdapter(BaseAdapter):
    def __init__(self):
        self.urls = []

    def send(self, request, **kwargs):
        self.urls.append(request.url)
        response = requests.Response()
        response.status_code = 307
        response.headers["Location"] = "http://127.0.0.1:8000/admin"
        response._content = b""
        response.request = request
        response.url = request.url
        return response

    def close(self):
        pass


def test_push_redirect_cannot_reach_internal_network():
    adapter = RedirectAdapter()
    with _PushSession() as session:
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        response = session.post("https://fcm.googleapis.com/send/a", data=b"encrypted")
    assert response.status_code == 307
    assert adapter.urls == ["https://fcm.googleapis.com/send/a"]


def test_redirect_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        "orot_collector.push_sender.webpush",
        lambda **kwargs: SimpleNamespace(status_code=307),
    )
    from orot_collector.push_sender import WebPushException

    with pytest.raises(WebPushException):
        _send_push()


@pytest.mark.asyncio
async def test_malformed_stored_endpoint_does_not_crash_sender(monkeypatch):
    monkeypatch.setattr(
        "orot_collector.push_sender.get_settings",
        lambda: SimpleNamespace(
            push_enabled=True, vapid_private_key="unused", vapid_subject="mailto:test@example.com"
        ),
    )
    result = await WebPushSender().send(
        DeviceToken(token="https://[broken", p256dh="key", auth="auth"), {}
    )
    assert result.outcome == SendOutcome.GONE


@pytest.mark.asyncio
async def test_exception_details_do_not_leak_subscription_secrets(monkeypatch):
    monkeypatch.setattr(
        "orot_collector.push_sender.get_settings",
        lambda: SimpleNamespace(
            push_enabled=True, vapid_private_key="unused", vapid_subject="mailto:test@example.com"
        ),
    )

    def fail(**kwargs):
        raise ValueError("secret-endpoint-and-key")

    monkeypatch.setattr("orot_collector.push_sender._send_push", fail)
    result = await WebPushSender().send(
        DeviceToken(token="https://fcm.googleapis.com/send/a", p256dh="key", auth="auth"), {}
    )
    assert result.outcome == SendOutcome.FAILED
    assert result.error == "ValueError"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 410, 429, 500, 503])
async def test_push_service_status_classification(monkeypatch, status):
    from orot_collector.push_sender import WebPushException

    monkeypatch.setattr(
        "orot_collector.push_sender.get_settings",
        lambda: SimpleNamespace(
            push_enabled=True, vapid_private_key="unused", vapid_subject="mailto:test@example.com"
        ),
    )

    def fail(**kwargs):
        raise WebPushException(
            "synthetic service error", response=SimpleNamespace(status_code=status)
        )

    monkeypatch.setattr("orot_collector.push_sender._send_push", fail)
    result = await WebPushSender().send(
        DeviceToken(token="https://fcm.googleapis.com/send/a", p256dh="key", auth="auth"), {}
    )
    assert result.outcome == (SendOutcome.GONE if status in {404, 410} else SendOutcome.FAILED)
