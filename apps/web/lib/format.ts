/** 표시용 서식. **DB 는 UTC, 화면은 KST** 다 (CLAUDE.md §6). */

const KST = "Asia/Seoul";

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("ko-KR", {
    timeZone: KST,
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ko-KR", {
    timeZone: KST,
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** "3일 뒤", "2시간 뒤" 처럼 남은 시간을 사람이 읽는 말로. */
export function relativeFromNow(iso: string): string {
  const diffMs = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(diffMs);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  const formatter = new Intl.RelativeTimeFormat("ko", { numeric: "auto" });
  if (abs < hour) return formatter.format(Math.round(diffMs / minute), "minute");
  if (abs < day) return formatter.format(Math.round(diffMs / hour), "hour");
  return formatter.format(Math.round(diffMs / day), "day");
}

/** 발매 일정을 한 줄로: "실리카겔 — Machine Boy (2LP)" */
export function releaseLabel(r: { artist_name: string | null; title: string; format: string | null }) {
  const head = r.artist_name ? `${r.artist_name} — ${r.title}` : r.title;
  return r.format ? `${head} (${r.format})` : head;
}

/**
 * 이벤트 종류를 사람이 읽는 말로.
 *
 * 알 수 없는 값이면 **원문을 그대로** 돌려준다. 빈 칸을 보여 주면 화면에서
 * 사라진 것처럼 보여, 새 이벤트 종류가 늘었을 때 아무도 알아채지 못한다.
 * 서버(`orot_core.notifications`, `routers/rss.py`)와 같은 말을 쓴다 —
 * 알림에서 "일정 변동"이라고 본 것이 피드에서 다른 말이면 같은 일로 읽히지 않는다.
 */
const EVENT_LABELS: Record<string, string> = {
  SCHEDULE_ADDED: "일정 등록",
  SCHEDULE_CHANGED: "일정 변동",
  PREORDER_OPENS_SOON: "예약 임박",
  PREORDER_OPEN: "예약 시작",
  RELEASED: "발매",
  NEW_LISTING: "신규 등록",
  RESTOCK: "재입고",
  SOLD_OUT: "품절",
  PRICE_DROP: "가격 인하",
  PRICE_RISE: "가격 인상",
  DELISTED: "판매 종료",
};

export function eventLabel(eventType: string | null): string {
  if (!eventType) return "알림";
  return EVENT_LABELS[eventType] ?? eventType;
}
