"""Web Push 구독 계약 (T-114, ADR-0006).

DB 없이 스키마와 설정 계약만 검사한다.
구독·해지 흐름은 컨테이너에서 실제 요청으로 검증했다.
"""

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from orot_core.settings import Settings
from pydantic import ValidationError

from orot_api.schemas.push import PushSubscriptionIn, PushUnsubscribeIn

PUBLIC_KEY = (
    base64.urlsafe_b64encode(
        ec.derive_private_key(1, ec.SECP256R1())
        .public_key()
        .public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    )
    .decode()
    .rstrip("=")
)
AUTH = base64.urlsafe_b64encode(bytes(range(16))).decode().rstrip("=")


def test_subscription_accepts_browser_json_shape() -> None:
    """브라우저의 `PushSubscription.toJSON()` 을 그대로 받는다.

    형태를 바꾸면 클라이언트가 변환 코드를 써야 하고, 그만큼 틀릴 자리가 생긴다.
    """
    payload = PushSubscriptionIn.model_validate(
        {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
            "keys": {"p256dh": PUBLIC_KEY, "auth": AUTH},
        }
    )
    assert payload.endpoint.endswith("/abc")
    assert payload.keys.p256dh == PUBLIC_KEY


@pytest.mark.parametrize(
    "bad",
    [
        {"endpoint": "", "keys": {"p256dh": "a", "auth": "b"}},
        {"endpoint": "https://x", "keys": {"p256dh": "", "auth": "b"}},
        {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": ""}},
        {"endpoint": "https://x"},
    ],
)
def test_incomplete_subscription_is_rejected(bad: dict[str, object]) -> None:
    """키가 하나라도 없으면 암호화를 못 해 발송이 불가능하다 (RFC 8291)."""
    with pytest.raises(ValidationError):
        PushSubscriptionIn.model_validate(bad)


def test_unsubscribe_needs_only_endpoint() -> None:
    assert PushUnsubscribeIn(endpoint="https://x").endpoint == "https://x"


def test_push_disabled_when_keys_missing() -> None:
    """키가 없으면 푸시만 꺼지고 나머지 기능은 정상이어야 한다.

    오류로 다루면 키 없이는 서버가 아예 못 뜬다.
    """
    assert (
        Settings(vapid_public_key="", vapid_private_key="", vapid_subject="").push_enabled is False
    )
    assert (
        Settings(vapid_public_key="pub", vapid_private_key="", vapid_subject="s").push_enabled
        is False
    )


def test_push_enabled_with_all_three() -> None:
    settings = Settings(
        vapid_public_key="pub", vapid_private_key="priv", vapid_subject="mailto:a@b.c"
    )
    assert settings.push_enabled is True
