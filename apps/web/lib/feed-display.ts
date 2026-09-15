import type { Release } from "./api";

/** Status describes the schedule now, independently of past notification events. */
export function feedDisplay(release: Release, now: number) {
  const opens = release.preorder_opens_at;
  const closes = release.preorder_closes_at;
  if (release.schedule_status === "TBA") {
    return { status: "발매일 미정", at: null, dateOnly: false, label: "발매일 미정", future: false };
  }
  if (release.schedule_status === "ON_SALE") {
    const status = closes && now >= Date.parse(closes) ? "판매 종료" : "판매 중";
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
