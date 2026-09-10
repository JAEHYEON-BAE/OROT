"""수집기 CLI (T-001 스캐폴딩).

실제 수집은 T-005(fetcher) / T-007(어댑터) / T-009(파이프라인) 에서 구현된다.
현재는 명령 표면과 컨테이너 기동만 확인할 수 있다.
"""

import asyncio
import time
from typing import Final

import httpx
import typer
from sqlalchemy import select
from vinyl_core import __version__ as core_version
from vinyl_core.adapters import get_adapter
from vinyl_core.db import session_scope
from vinyl_core.enums import DevicePlatform, EventType
from vinyl_core.logging import configure_logging
from vinyl_core.models import DeviceToken, ListingEvent, Release
from vinyl_core.notifications import SendOutcome, build_payload
from vinyl_core.seed import seed_sources
from vinyl_core.settings import get_settings
from vinyl_core.testing import ACCEPTED

from vinyl_collector.bridge import FetcherPageAdapter
from vinyl_collector.fetcher import Fetcher, FetchOutcome, SourceBlockedError
from vinyl_collector.push_sender import WebPushSender
from vinyl_collector.scheduler import run as run_scheduler

app = typer.Typer(help="Vinyl Radar 수집기", no_args_is_help=True)


@app.command()
def version() -> None:
    """버전과 유효 설정을 출력한다."""
    configure_logging()
    settings = get_settings()
    typer.echo(f"vinyl-collector {core_version}")
    typer.echo(f"environment      : {settings.environment}")
    typer.echo(f"user-agent       : {settings.crawler_user_agent}")
    typer.echo(f"rate limit (rps) : {settings.crawler_rate_limit_rps}")
    typer.echo(f"max concurrency  : {settings.crawler_max_concurrency}")


@app.command()
def scheduler() -> None:
    """상주 스케줄러를 실행한다 (T-111).

    1분마다 `preorder_opens_at` 을 살펴 시각 기반 이벤트를 만든다.
    """
    asyncio.run(run_scheduler())


@app.command()
def seed() -> None:
    """시드 데이터를 적재한다. 몇 번을 다시 실행해도 결과가 같다.

    이미 존재하는 소스의 운영 상태(`is_enabled` 등)는 덮어쓰지 않는다.
    """
    configure_logging()

    async def _run() -> int:
        async with session_scope() as session:
            return await seed_sources(session)

    count = asyncio.run(_run())
    typer.echo(f"sources 시드 완료: {count}건")
    # 아티스트 별칭(aliases.yaml)은 T-019 에서 이 명령에 추가된다.


# 케이스를 지정하지 않았을 때 보내는 기본 알림.
_DEFAULT_CASE: Final = "기본"

# 연속 발송 사이의 간격. 푸시 서비스에 한꺼번에 몰아넣지 않는다.
_SEND_GAP_SECONDS: Final = 0.5


@app.command("test-push")
def test_push(
    case: str = typer.Option(
        "",
        "--case",
        help="엣지 케이스 이름(쉼표로 여러 개), 또는 all. 생략하면 기본 알림 1건",
    ),
    event_type: str = typer.Option(
        EventType.PREORDER_OPEN.value,
        "--event",
        help="이벤트 종류 (SCHEDULE_ADDED / PREORDER_OPENS_SOON / PREORDER_OPEN / RELEASED)",
    ),
    list_cases: bool = typer.Option(False, "--list", help="보낼 수 있는 케이스 이름을 출력"),
    dry_run: bool = typer.Option(False, "--dry-run", help="보내지 않고 대상과 페이로드만 출력"),
) -> None:
    """등록된 모든 구독에 시험 알림을 보낸다.

    **DB 를 전혀 바꾸지 않는다** — 발매도 이벤트도 배송 기록도 만들지 않는다.
    확인하려는 것은 하나다: *이 기기까지 실제로 도착하는가.*

    스케줄러를 통한 경로와 분리해 두는 이유는, 알림이 안 왔을 때 원인이
    **전송(VAPID·키·네트워크)** 인지 **로직(이벤트 생성·발송 대상 선정)** 인지
    구분할 수 없으면 어디를 봐야 할지 알 수 없기 때문이다.

    `--case` 는 `vinyl_core.testing` 의 카탈로그를 그대로 쓴다. 이모지·긴 제목·
    개행처럼 **실제 기기에서만 확인되는 표시 문제**가 있어서, 같은 케이스를
    화면에서도 기기에서도 통과시킨다.
    """
    configure_logging()
    settings = get_settings()

    if list_cases:
        typer.echo(f"  {_DEFAULT_CASE:26s} 기본 시험 알림")
        for edge in ACCEPTED:
            typer.echo(f"  {edge.name:26s} {edge.what}")
        return

    if not settings.push_enabled:
        typer.echo("푸시가 설정되어 있지 않습니다 (.env 의 VAPID_* 확인).", err=True)
        raise typer.Exit(code=1)

    if event_type not in {e.value for e in EventType}:
        typer.echo(f"알 수 없는 이벤트 종류: {event_type}", err=True)
        raise typer.Exit(code=1)

    try:
        cases = _resolve_cases(case)
    except KeyError:
        typer.echo(f"알 수 없는 케이스: {case}  (--list 로 목록 확인)", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"VAPID subject : {settings.vapid_subject}")
    typer.echo(f"알림 클릭 목적지: {settings.public_web_url}")
    if "localhost" in settings.public_web_url:
        # 발송은 성공하는데 알림을 눌러도 아무 데도 못 가는 상태를 미리 알린다.
        typer.echo(
            "  ⚠ localhost 는 휴대폰에서 열리지 않습니다. "
            "PUBLIC_WEB_URL 을 공개 주소로 바꾸십시오.",
            err=True,
        )
    typer.echo("")

    sent, failed, gone = asyncio.run(
        _test_push(cases=cases, event_type=event_type, dry_run=dry_run)
    )
    typer.echo("")
    typer.echo(f"전송 {sent}건 / 실패 {failed}건 / 만료 {gone}건")
    if failed or gone:
        raise typer.Exit(code=1)


def _resolve_cases(case: str) -> list[str]:
    """`--case` 인자를 보낼 케이스 이름 목록으로. 쉼표로 여러 개를 줄 수 있다."""
    if not case:
        return [_DEFAULT_CASE]
    if case == "all":
        return [c.name for c in ACCEPTED]
    names = [part.strip() for part in case.split(",") if part.strip()]
    known = {c.name for c in ACCEPTED} | {_DEFAULT_CASE}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise KeyError(", ".join(unknown))
    return names


def _fake_release_id(name: str) -> int:
    """케이스마다 **고정된** 가짜 발매 id.

    `build_payload` 의 `tag` 가 `release-<id>` 라 id 가 같으면 알림이 서로를
    덮어쓴다. 호출 순서로 정하면 명령을 따로 실행할 때마다 같은 id 가 나와
    **앞서 보낸 시험 알림이 사라진다.** 카탈로그 안의 위치로 고정한다.
    """
    if name == _DEFAULT_CASE:
        return 0
    return next(i for i, c in enumerate(ACCEPTED, start=1) if c.name == name)


def _release_for(name: str) -> tuple[Release, str | None]:
    """케이스 이름으로 저장하지 않는 임시 `Release` 를 만든다."""
    index = _fake_release_id(name)
    if name == _DEFAULT_CASE:
        return (
            Release(
                id=index,
                title="시험 알림 — 도착하면 성공입니다",
                format="LP",
                is_limited=True,
                variant=None,
            ),
            "Vinyl Radar",
        )

    edge = next(c for c in ACCEPTED if c.name == name)
    # 카탈로그의 원본 입력을 그대로 쓴다. 검증(`ReleaseIn`)은 `vinyl_api` 에 있고
    # 수집기가 그쪽을 임포트하면 의존 방향이 뒤집힌다 — 여기서 확인하려는 것은
    # 검증이 아니라 **기기에서 어떻게 보이는가** 이므로 원본이면 충분하다.
    payload = edge.payload
    return (
        Release(
            id=index,
            title=str(payload["title"]),
            format=payload.get("format"),
            is_limited=bool(payload.get("is_limited", False)),
            variant=payload.get("variant"),
        ),
        payload.get("artist_name"),
    )


async def _test_push(*, cases: list[str], event_type: str, dry_run: bool) -> tuple[int, int, int]:
    """실제 발송 경로를 그대로 태운다 — 페이로드도 `build_payload` 가 만든다."""
    base_url = get_settings().public_web_url
    event = ListingEvent(event_type=event_type)

    payloads: list[tuple[str, dict[str, object]]] = []
    for name in cases:
        # 저장하지 않는 임시 객체다. 세션에 넣지 않으므로 DB 에 남지 않는다.
        release, artist_name = _release_for(name)
        payloads.append((name, build_payload(event, release, artist_name, base_url)))

    for name, payload in payloads:
        typer.echo(f"[{name}]")
        typer.echo(f"  제목 : {payload['title']}")
        typer.echo(f"  본문 : {payload['body']}")
        typer.echo(f"  링크 : {payload['url']}   tag={payload['tag']}")
    typer.echo("")

    sent = failed = gone = 0
    async with session_scope() as session:
        subscriptions = list(
            await session.scalars(
                select(DeviceToken).where(
                    DeviceToken.is_active.is_(True),
                    DeviceToken.platform == DevicePlatform.WEB.value,
                )
            )
        )
        if not subscriptions:
            typer.echo("활성 구독이 없습니다. 먼저 /subscribe 에서 알림을 켜 주십시오.", err=True)
            return 0, 0, 0

        sender = WebPushSender()
        for subscription in subscriptions:
            # 엔드포인트 전체는 길고 그 자체가 비밀에 가깝다. 어느 서비스인지만 보인다.
            host = subscription.token.split("/")[2] if "//" in subscription.token else "?"
            for name, payload in payloads:
                label = f"#{subscription.id} {host} [{name}]"
                if dry_run:
                    typer.echo(f"  {label:52s} (보내지 않음)")
                    continue

                result = await sender.send(subscription, payload)
                if result.outcome is SendOutcome.SENT:
                    sent += 1
                    typer.echo(f"  {label:52s} 전송됨")
                elif result.outcome is SendOutcome.GONE:
                    gone += 1
                    # 구독을 끄지 않는다 — 진단 명령이 데이터를 바꾸면 안 된다.
                    typer.echo(f"  {label:52s} 구독 만료 ({result.detail})", err=True)
                else:
                    failed += 1
                    typer.echo(f"  {label:52s} 실패 ({result.detail})", err=True)

                if len(payloads) > 1:
                    await asyncio.sleep(_SEND_GAP_SECONDS)

    return sent, failed, gone


@app.command()
def run(
    source: str = typer.Option(..., "--source", help="소스 ID (예: gimbab)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="DB 에 쓰지 않고 파싱 결과만 출력"),
    limit: int = typer.Option(5, "--limit", help="처리할 최대 상품 수"),
) -> None:
    """단일 소스를 수집한다.

    `--dry-run` 은 **DB 를 전혀 건드리지 않고** 수집 경로만 확인한다.
    DB 적재는 T-009(파이프라인)에서 구현된다.
    """
    if not dry_run:
        typer.echo(
            "[미구현] DB 적재는 T-009 에서 구현됩니다. 지금은 --dry-run 만 사용할 수 있습니다.",
            err=True,
        )
        raise typer.Exit(code=1)

    configure_logging()
    asyncio.run(_dry_run(source, limit))


async def _dry_run(source_id: str, limit: int) -> None:
    """실제 사이트에서 몇 건만 가져와 파싱 결과를 출력한다 (DB 미사용)."""
    settings = get_settings()
    adapter = get_adapter(source_id)

    typer.echo(f"소스        : {adapter.display_name} ({source_id})")
    typer.echo(f"User-Agent  : {settings.crawler_user_agent}")
    typer.echo(
        f"속도 제한   : {settings.crawler_rate_limit_rps} req/s "
        f"(요청 간 최소 {1 / settings.crawler_rate_limit_rps:.1f}초)"
    )
    typer.echo(f"최대 수집   : {limit}건  |  DB 쓰기: 없음")
    typer.echo("")

    timeout = httpx.Timeout(20.0)
    started = time.monotonic()
    parsed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        fetcher = Fetcher(
            source_id=source_id,
            user_agent=settings.crawler_user_agent,
            client=client,
            rps=settings.crawler_rate_limit_rps,
            max_concurrency=settings.crawler_max_concurrency,
        )
        page_fetcher = FetcherPageAdapter(fetcher)
        adapter = type(adapter)(page_fetcher)  # PageFetcher 주입

        try:
            async for page_url in adapter.discover():
                if parsed >= limit:
                    break

                elapsed = time.monotonic() - started
                result = await fetcher.fetch(page_url)
                if result.outcome is not FetchOutcome.FETCHED or result.body is None:
                    failed += 1
                    typer.echo(f"[{elapsed:6.1f}s] {result.outcome.value:12s} {page_url}")
                    continue

                items = await adapter.parse_page(page_url, result.body)
                if not items:
                    failed += 1
                    typer.echo(f"[{elapsed:6.1f}s] {'PARSE_FAIL':12s} {page_url}")
                    continue

                typer.echo(
                    f"[{elapsed:6.1f}s] 목록 1건 → 상품 {len(items)}건  "
                    f"hash={(result.content_hash or '')[:12]}  {page_url}"
                )
                for item in items:
                    if parsed >= limit:
                        break
                    # 제목·URL 을 자르지 않는다. dry-run 의 목적이 원문 확인이고,
                    # 잘리는 뒷부분(예약 표기·포맷 힌트)이 정규화(T-008)의 입력이다.
                    parsed += 1
                    price = f"{int(item.price_krw):,}원" if item.price_krw is not None else "-"
                    typer.echo(f"    {item.stock_status.value:9s} {price:>11s}  {item.title_raw}")
        except SourceBlockedError as exc:
            # §3.4: 차단이 확인되면 즉시 멈춘다. 소스 비활성화는 T-009/T-012 의 몫이다.
            typer.echo(f"\n차단 감지: {exc}", err=True)
            raise typer.Exit(code=2) from exc

    total = time.monotonic() - started
    requests = fetcher.request_count
    min_interval = 1.0 / settings.crawler_rate_limit_rps
    # 요청 n 회의 간격은 n-1 개다. 첫 요청은 t=0 에 나가므로
    # n/경과 로 나누면 속도가 실제보다 부풀려진다.
    average_gap = total / (requests - 1) if requests > 1 else float("inf")
    verdict = "준수" if average_gap >= min_interval else "초과"
    typer.echo("")
    typer.echo(f"파싱 성공 {parsed}건 / 실패 {failed}건")
    typer.echo(f"총 요청 {requests}회 (robots.txt 포함), {total:.1f}초 소요")
    typer.echo(f"평균 요청 간격 {average_gap:.2f}초 / 최소 {min_interval:.1f}초 → §3.4 {verdict}")


if __name__ == "__main__":
    app()
