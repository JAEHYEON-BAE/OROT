"""Slack 으로 운영자 알림 보내기 (T-116).

Incoming Webhook 하나만 쓴다. OAuth 앱·봇 토큰·스코프가 필요 없고, 받는 쪽에서
채널을 바꾸거나 끊는 것도 웹훅을 지우면 끝이라 운영자 1명 단계에 맞는다.

**웹훅 URL 은 비밀이다.** 아는 사람은 누구나 그 채널에 글을 쓸 수 있으므로
로그에도 오류 메시지에도 남기지 않는다.
"""

from typing import Final

import httpx
import structlog
from orot_core.alerts import Alert
from orot_core.settings import get_settings

log = structlog.get_logger(__name__)

# 알림은 부가 기능이다. 오래 매달려 스케줄러 주기를 잡아먹으면 안 된다.
REQUEST_TIMEOUT: Final = 5.0

# Slack 블록 텍스트 상한(3000자)보다 넉넉히 아래로 자른다.
MAX_DETAIL: Final = 1500


class SlackAlerter:
    """`orot_core.alerts.AlertSender` 구현."""

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.slack_webhook_url.strip()
        self._enabled = settings.alerts_enabled
        self._environment = settings.environment
        if not self._enabled:
            log.info("alerts.disabled", reason="SLACK_WEBHOOK_URL 이 설정되지 않음")

    async def send(self, alert: Alert) -> bool:
        if not self._enabled:
            return False

        detail = alert.detail[:MAX_DETAIL]
        payload = {
            # `text` 는 알림 미리보기(푸시·목록)에 쓰인다. 블록만 넣으면 미리보기가 빈다.
            "text": f"[OROT/{self._environment}] {alert.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{alert.title}*\n{detail}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"`{self._environment}` · `{alert.key}`",
                        }
                    ],
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(self._url, json=payload)
        except Exception as exc:
            # 예외 문자열에 URL 이 섞인다. 클래스명만 남긴다.
            log.warning("alert.slack_failed", error=type(exc).__name__)
            return False

        if response.status_code != 200:
            # 본문은 "invalid_token" 같은 짧은 문자열이라 그대로 둬도 URL 이 새지 않는다.
            log.warning(
                "alert.slack_rejected", status=response.status_code, body=response.text[:80]
            )
            return False

        log.info("alert.sent", key=alert.key)
        return True
