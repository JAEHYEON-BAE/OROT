import type { Release } from "./api";

/**
 * 판매 중인 일정의 상태. **마감이 지났는지는 지금 시각에 달려 있다.**
 *
 * 피드와 상세가 각자 판정하면 같은 일정이 두 화면에서 다르게 보인다 —
 * 한쪽만 고쳐지고 다른 쪽이 조용히 어긋나는 종류의 버그라 한곳에 모은다.
 *
 * `now` 를 인자로 받는 이유는 시험에서 시각을 고정하기 위해서다. 기본값을 두는 것은
 * 상세 화면처럼 서버가 준 기준 시각이 없는 곳을 위한 것인데, 그 호출은 `relativeFromNow`
 * 와 마찬가지로 **요청마다 렌더되는 화면**(`dynamic = "force-dynamic"`)에서만 쓴다.
 */
export function onSaleStatus(closesAt: string | null | undefined, now = Date.now()): string {
  return closesAt && now >= Date.parse(closesAt) ? "판매 종료" : "판매 중";
}

/** Status describes the schedule now, independently of past notification events. */
export function feedDisplay(release: Release, now: number) {
  const opens = release.preorder_opens_at;
  const closes = release.preorder_closes_at;
  if (release.schedule_status === "TBA") {
    return { status: "발매일 미정", at: null, dateOnly: false, label: "발매일 미정", future: false };
  }
  if (release.schedule_status === "ON_SALE") {
    const status = onSaleStatus(closes, now);
    return { status, at: null, dateOnly: false, label: status, future: false };
  }
  if (opens) {
    const start = Date.parse(opens);
    const status = now < start
      ? "예약 예정"
      : closes && now >= Date.parse(closes) ? "예약 마감" : "예약 진행 중";
    return { status, at: opens, dateOnly: false, label: "예약 시작", future: now < start };
  }
  if (release.release_date) {
    const start = Date.parse(`${release.release_date}T00:00:00+09:00`);
    return {
      status: now < start ? "발매 예정" : "발매됨",
      at: release.release_date, dateOnly: true, label: "발매일", future: now < start,
    };
  }
  return { status: "일정 미정", at: null, dateOnly: false, label: "일정 미정", future: false };
}
