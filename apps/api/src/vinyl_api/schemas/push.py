"""Web Push 구독 모델 (ADR-0006)."""

import base64
import binascii
import re

from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, Field, field_validator
from vinyl_core.notifications import (
    MAX_ENDPOINT_LENGTH,
    MAX_PUSH_KEY_LENGTH,
    is_allowed_push_endpoint,
)


class PushKeys(BaseModel):
    """브라우저가 주는 암호화 키 (RFC 8291)."""

    p256dh: str = Field(min_length=1, max_length=MAX_PUSH_KEY_LENGTH, description="구독 공개키")
    auth: str = Field(min_length=1, max_length=MAX_PUSH_KEY_LENGTH, description="인증 시크릿")

    @field_validator("p256dh", "auth")
    @classmethod
    def _valid_base64url(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
            raise ValueError("올바른 base64url 키가 필요합니다.")
        try:
            base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("올바른 base64url 키가 필요합니다.") from exc
        return value

    @field_validator("p256dh")
    @classmethod
    def _valid_curve_point(cls, value: str) -> str:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(raw) != 65 or raw[0] != 4:
            raise ValueError("p256dh 는 65바이트 비압축 P-256 공개키여야 합니다.")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        return value

    @field_validator("auth")
    @classmethod
    def _valid_auth(cls, value: str) -> str:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(raw) != 16:
            raise ValueError("auth 는 16바이트여야 합니다.")
        return value


class PushSubscriptionIn(BaseModel):
    """`PushSubscription.toJSON()` 이 그대로 들어온다.

    브라우저가 만들어 주는 형태를 그대로 받으므로 클라이언트 코드가 단순해진다.
    """

    endpoint: str = Field(
        min_length=1, max_length=MAX_ENDPOINT_LENGTH, description="푸시 서비스 엔드포인트 URL"
    )
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def _known_push_service(cls, v: str) -> str:
        """알려진 푸시 서비스로 가는 https 주소만 받는다 (T-130).

        **이 검증이 없으면 SSRF 다.** 구독에는 인증이 없으므로, 임의 URL 을 등록하면
        인터넷의 누구나 이 서버가 내부망으로 요청을 보내게 만들 수 있다.
        """
        if not is_allowed_push_endpoint(v):
            msg = "알려진 푸시 서비스의 https 주소가 아닙니다."
            raise ValueError(msg)
        return v


class PushUnsubscribeIn(BaseModel):
    """해지에는 엔드포인트만 있으면 된다.

    여기서는 **호스트를 검사하지 않는다.** 조회만 하고 그 주소로 요청을 보내지
    않으므로 위험이 없고, 목록이 바뀌기 전에 등록된 구독도 해지할 수 있어야 한다.
    """

    endpoint: str = Field(min_length=1, max_length=MAX_ENDPOINT_LENGTH)


class PushPublicKeyOut(BaseModel):
    """브라우저가 구독할 때 쓰는 VAPID 공개키."""

    public_key: str
    enabled: bool = Field(description="서버에 키가 설정되어 있는지")


class PushSubscriptionOut(BaseModel):
    id: int
    endpoint: str
    created: bool = Field(description="새로 만들어졌는지(False 면 이미 있던 구독)")
