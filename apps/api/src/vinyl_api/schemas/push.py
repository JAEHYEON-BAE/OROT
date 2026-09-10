"""Web Push 구독 모델 (ADR-0006)."""

from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    """브라우저가 주는 암호화 키 (RFC 8291)."""

    p256dh: str = Field(min_length=1, description="구독 공개키")
    auth: str = Field(min_length=1, description="인증 시크릿")


class PushSubscriptionIn(BaseModel):
    """`PushSubscription.toJSON()` 이 그대로 들어온다.

    브라우저가 만들어 주는 형태를 그대로 받으므로 클라이언트 코드가 단순해진다.
    """

    endpoint: str = Field(min_length=1, description="푸시 서비스 엔드포인트 URL")
    keys: PushKeys


class PushUnsubscribeIn(BaseModel):
    """해지에는 엔드포인트만 있으면 된다."""

    endpoint: str = Field(min_length=1)


class PushPublicKeyOut(BaseModel):
    """브라우저가 구독할 때 쓰는 VAPID 공개키."""

    public_key: str
    enabled: bool = Field(description="서버에 키가 설정되어 있는지")


class PushSubscriptionOut(BaseModel):
    id: int
    endpoint: str
    created: bool = Field(description="새로 만들어졌는지(False 면 이미 있던 구독)")
