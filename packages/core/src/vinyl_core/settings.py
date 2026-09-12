"""환경 변수 기반 설정.

블루프린트 §3.4 의 수집 제약(요청 속도·User-Agent)은 여기서 기본값을 강제한다.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 블루프린트 §3.4: 소스별 최대 0.5 req/s. 코드에서 상한을 강제한다.
MAX_ALLOWED_RATE_LIMIT_RPS = 0.5

# 로컬 개발용 기본 운영자 키. 이 값이 로컬 밖에서 쓰이면 기동을 막는다.
DEV_ADMIN_KEY = "change-me-local-dev-only"


class Settings(BaseSettings):
    """프로세스 전역 설정.

    **비밀은 `repr` 에 남기지 않는다** (`repr=False`).

    `log.exception` 의 트레이스백 렌더러가 지역 변수를 `repr()` 로 찍는다.
    `settings` 를 지역 변수로 들고 있는 함수가 예외를 던지면 **운영자 키·VAPID
    개인키·DB 암호·웹훅 URL 이 통째로 로그에 박힌다.** 실제로 스케줄러 주기 실패에서
    그렇게 나갔다 (T-116 검증 중 발견).

    로컬에서는 로그가 컨테이너 안에 머물지만, 로그를 수집하는 환경(CloudWatch 등)으로
    옮기면 그대로 사고가 된다.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    # `repr=False` — 아래 "비밀은 repr 에 남기지 않는다" 참조. 이 값에는 DB 암호가 들어 있다.
    database_url: str = Field(
        default="postgresql+asyncpg://vinyl:vinyl_local_dev_only@postgres:5432/vinyl_radar",
        repr=False,
    )

    # 운영자 API 의 유일한 인증 수단 (ADR-0005). 계정 시스템을 쓰지 않는다.
    # 이 키가 새면 누구나 일정을 등록할 수 있으므로 운영 시 반드시 교체한다.
    # 아래 `_reject_default_key_outside_local` 이 그 주석을 강제한다.
    admin_api_key: str = Field(default=DEV_ADMIN_KEY, repr=False)

    # ─── Web Push (VAPID, RFC 8292 / ADR-0006) ──────────────────
    # 자체 생성 키 쌍이라 외부 계정도 비용도 없다.
    # 비어 있으면 푸시 기능만 꺼지고 나머지는 정상 동작한다 (구독·발송이 no-op).
    vapid_public_key: str = ""
    vapid_private_key: str = Field(default="", repr=False)
    # 푸시 서비스(구글/애플)가 문제 발생 시 연락할 주소.
    # **요청 JWT 에 담겨 외부로 전송된다.**
    vapid_subject: str = ""

    # 알림을 눌렀을 때 이동할 주소. 브라우저에서 접근 가능한 공개 주소여야 한다.
    public_web_url: str = "http://localhost:3000"

    # ─── 운영자 알림 (T-116) ────────────────────────────────────
    # Slack Incoming Webhook URL. 비어 있으면 알림만 꺼지고 발송은 정상 동작한다.
    # **이 URL 자체가 비밀이다** — 아는 사람은 누구나 그 채널에 글을 쓸 수 있다.
    slack_webhook_url: str = Field(default="", repr=False)

    @property
    def alerts_enabled(self) -> bool:
        return bool(self.slack_webhook_url.strip())

    @property
    def push_enabled(self) -> bool:
        """키가 모두 있어야 푸시를 쓸 수 있다."""
        return bool(self.vapid_public_key and self.vapid_private_key and self.vapid_subject)

    crawler_user_agent: str = "VinylRadar/1.0 (+https://example.com/about; contact@example.com)"
    crawler_rate_limit_rps: float = Field(default=0.5, gt=0)
    crawler_max_concurrency: int = Field(default=2, ge=1, le=2)

    @model_validator(mode="after")
    def _reject_default_key_outside_local(self) -> "Settings":
        """운영 환경에서 기본 운영자 키를 쓰면 **기동을 실패시킨다**.

        이 키 하나가 운영자 API 의 전부다 (ADR-0005). 공개된 서버에서 기본값이
        쓰이면 누구나 일정을 등록·삭제·공개할 수 있다. 조용히 도는 것보다
        기동에서 죽는 편이 낫다 — 죽으면 바로 알아채지만, 새는 것은 모른다.

        `compose.yaml` 이 `ADMIN_API_KEY` 를 필수로 넘기지 않아 컨테이너가 이
        기본값을 쓰고 있던 적이 실제로 있었다 (T-120).
        """
        if not self.admin_api_key.strip():
            raise ValueError("ADMIN_API_KEY 는 비어 있을 수 없습니다.")
        if self.environment != "local" and (
            self.admin_api_key == DEV_ADMIN_KEY or len(self.admin_api_key.strip()) < 32
        ):
            msg = (
                "local 외부에서는 ADMIN_API_KEY 에 32자 이상의 비밀 키가 필요합니다. "
                "`openssl rand -base64 32` 로 생성해 .env 에 설정하십시오."
            )
            raise ValueError(msg)
        return self

    @field_validator("crawler_rate_limit_rps")
    @classmethod
    def _cap_rate_limit(cls, v: float) -> float:
        """설정 실수로 블루프린트 §3.4 상한을 넘기지 못하게 막는다."""
        if v > MAX_ALLOWED_RATE_LIMIT_RPS:
            msg = (
                f"crawler_rate_limit_rps={v} 는 블루프린트 §3.4 상한 "
                f"{MAX_ALLOWED_RATE_LIMIT_RPS} req/s 를 초과합니다."
            )
            raise ValueError(msg)
        return v

    @field_validator("crawler_user_agent")
    @classmethod
    def _require_contact(cls, v: str) -> str:
        """블루프린트 §3.4: User-Agent 는 정체와 연락처를 밝혀야 한다."""
        if "+http" not in v or "@" not in v:
            msg = "crawler_user_agent 에는 소개 URL(+http...) 과 연락처(@) 가 모두 있어야 합니다."
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """설정 싱글턴."""
    return Settings()
