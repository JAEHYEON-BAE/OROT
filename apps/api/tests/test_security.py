"""Public-test security regressions; no DB writes or network requests."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from orot_core.notifications import is_allowed_push_endpoint
from orot_core.settings import Settings
from pydantic import ValidationError

from orot_api.deps import require_admin
from orot_api.schemas.push import PushKeys


@pytest.mark.parametrize("key", ["", " ", "\t"])
def test_blank_admin_key_never_starts(key):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, admin_api_key=key)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_public_mode_rejects_short_admin_key(environment):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=environment, admin_api_key="short")


@pytest.mark.asyncio
async def test_admin_dependency_fails_closed_even_with_invalid_settings(monkeypatch):
    monkeypatch.setattr("orot_api.deps.get_settings", lambda: SimpleNamespace(admin_api_key=""))
    with pytest.raises(HTTPException) as error:
        await require_admin(None)
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "https://fcm.googleapis.com:8443/send/a",
        "https://fcm.googleapis.com:bad/send/a",
        "https://user:password@fcm.googleapis.com/send/a",
        "https://fcm.googleapis.com/send/a#fragment",
        "https://fcm.googleapis.com/\nsecret",
        "https://fcm.googleapis.com/한글",
        "https://evil.example\\@fcm.googleapis.com/a",
        "https://fcm.googleapis.com.evil.example/a",
        "https://[invalid/a",
    ],
)
def test_ambiguous_push_urls_are_rejected(url):
    assert not is_allowed_push_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://web.push.apple.com/Qabc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://fcm.googleapis.com:443/fcm/send/abc",
    ],
)
def test_browser_push_endpoints_still_work(url):
    assert is_allowed_push_endpoint(url)


@pytest.mark.parametrize(
    "public_key,auth",
    [
        ("BPubKey", "AuthSecret"),
        ("!" * 87, "a" * 22),
        ("B" + "A" * 86, "a" * 22),  # invalid curve point
    ],
)
def test_unusable_push_keys_cannot_fill_delivery_queue(public_key, auth):
    with pytest.raises(ValidationError):
        PushKeys(p256dh=public_key, auth=auth)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "length,chunks,expected",
    [
        (b"9000", [], 413),
        (b"9" * 5000, [], 413),
        (b"2", [b"a" * 4096, b"b" * 4097], 413),
        (None, [b"a" * 4096, b"b" * 4097], 413),
        (None, [b"{", b"}"], 204),
    ],
)
async def test_api_body_limit_precedes_parser(length, chunks, expected):
    from orot_api.request_limits import PushBodyLimitMiddleware

    sent = []
    remaining = list(chunks)

    async def receive():
        chunk = remaining.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(remaining)}

    async def app(scope, receive, send):
        assert (await receive())["body"] == b"{}"
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):
        sent.append(message)

    await PushBodyLimitMiddleware(app)(
        {
            "type": "http",
            "path": "/v1/push/subscribe",
            "method": "POST",
            "headers": [] if length is None else [(b"content-length", length)],
        },
        receive,
        send,
    )
    assert sent[0]["status"] == expected


# ─── 설정 repr 유출 (T-116 검증 중 발견) ────────────────────────


@pytest.mark.parametrize(
    "field",
    ["admin_api_key", "vapid_private_key", "slack_webhook_url", "database_url"],
)
def test_secrets_never_appear_in_settings_repr(field: str) -> None:
    """**트레이스백이 지역 변수를 `repr()` 로 찍는다.**

    `settings` 를 들고 있는 함수가 예외를 던지면 운영자 키·VAPID 개인키·DB 암호·
    웹훅 URL 이 통째로 로그에 박힌다. 실제로 스케줄러 주기 실패에서 그렇게 나갔다.
    로그를 수집하는 환경으로 옮기면 그대로 사고가 된다.
    """
    marker = f"__{field}_should_not_be_printed__"
    settings = Settings(_env_file=None, **{field: marker, "environment": "local"})  # type: ignore[arg-type]

    assert getattr(settings, field) == marker, "값 자체는 읽을 수 있어야 한다"
    assert marker not in repr(settings)
    assert field not in repr(settings)


def test_non_secret_settings_stay_visible() -> None:
    """전부 가리면 로그로 디버깅할 수 없다. 비밀만 빼야 한다."""
    rendered = repr(Settings(_env_file=None, environment="local"))
    assert "environment=" in rendered
    assert "public_web_url=" in rendered
    assert "vapid_subject=" in rendered
