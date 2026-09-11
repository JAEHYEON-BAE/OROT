/**
 * 브라우저 푸시 구독 (T-117, ADR-0006).
 *
 * API 는 **같은 출처의 `/api/push/*` 프록시**를 통해 부른다 (ADR-0007).
 * 브라우저가 API 서버를 직접 부르면 CORS 허용 출처 목록을 환경마다 관리해야 하고,
 * 그 목록이 어긋나면 구독만 조용히 실패한다.
 */

export type PushState =
  | "loading"
  /** 이 브라우저가 푸시를 지원하지 않는다 (iOS Safari 의 홈 화면 밖 등). */
  | "unsupported"
  /** 서버에 VAPID 키가 없다. */
  | "server-disabled"
  /** 사용자가 알림을 차단했다. 코드로 되돌릴 수 없다. */
  | "denied"
  | "off"
  | "on";

/** 서비스워커 파일 경로. `public/` 에 두어 스코프가 사이트 전체가 된다. */
const SW_URL = "/sw.js";

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** iOS 는 홈 화면에 추가하기 전에는 푸시를 아예 지원하지 않는다. */
export function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  return (/iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
}

/** 홈 화면(또는 설치된 앱)에서 실행 중인가. */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS Safari 는 표준 display-mode 대신 이 비표준 속성을 쓴다.
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/**
 * base64url VAPID 공개키를 바이트 배열로.
 *
 * 규격상 문자열도 허용되지만 받아들이지 않는 브라우저가 있다.
 * `public/sw.js` 에 같은 함수가 있다 — 서비스워커는 앱 번들을 임포트할 수 없다.
 */
// 반환 타입에 ArrayBuffer 를 명시한다. 기본 Uint8Array 는 SharedArrayBuffer 도
// 포함해서 applicationServerKey(BufferSource) 에 넣을 수 없다.
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(padded);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export async function getPublicKey(): Promise<{ publicKey: string; enabled: boolean }> {
  const res = await fetch("/api/push/public-key", { cache: "no-store" });
  if (!res.ok) throw new Error(`공개키를 가져오지 못했습니다 (${res.status})`);
  const body = (await res.json()) as { public_key: string; enabled: boolean };
  return { publicKey: body.public_key, enabled: body.enabled };
}

/**
 * 서비스워커를 등록하고 준비될 때까지 기다린다.
 *
 * `updateViaCache: "none"` — HTTP 캐시가 낡은 서비스워커를 돌려주면 알림 로직
 * 수정이 며칠씩 반영되지 않는다.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register(SW_URL, { scope: "/", updateViaCache: "none" });
  return navigator.serviceWorker.ready;
}

export async function getExistingSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration(SW_URL);
  return (await registration?.pushManager.getSubscription()) ?? null;
}

/** 구독하고 서버에 등록한다. 이미 구독 중이면 그 구독을 다시 보낸다(서버가 갱신으로 처리). */
export async function subscribe(): Promise<PushSubscription> {
  // Ask before any await/network call so Safari retains the click gesture.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("알림 권한이 허용되지 않았습니다.");
  const { publicKey, enabled } = await getPublicKey();
  if (!enabled) throw new Error("서버에서 푸시 알림을 사용할 수 없습니다.");

  const registration = await registerServiceWorker();
  const existing = await registration.pushManager.getSubscription();
  const subscription =
    existing ??
    (await registration.pushManager.subscribe({
      // 푸시를 받으면 반드시 알림을 띄운다는 약속. 어기면 브라우저가 권한을 회수한다.
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }));

  try {
    const res = await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    if (!res.ok) throw new Error(`구독 등록에 실패했습니다 (${res.status})`);
  } catch (error) {
    // 서버가 모르는 구독은 알림이 오지 않는다. 브라우저 쪽만 남겨 두면
    // "구독 중"으로 보이는데 아무것도 안 오는 상태가 된다.
    if (!existing) await subscription.unsubscribe().catch(() => undefined);
    throw error;
  }
  return subscription;
}

/** 구독을 해지한다. 서버 쪽을 먼저 끄고 브라우저 구독을 취소한다. */
export async function unsubscribe(): Promise<void> {
  const subscription = await getExistingSubscription();
  if (!subscription) return;

  // 순서가 중요하다. 브라우저 구독을 먼저 취소하면 endpoint 를 잃어
  // 서버에 죽은 구독이 남고, 발송기가 계속 그쪽으로 요청을 보낸다.
  const response = await fetch("/api/push/subscribe", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: subscription.endpoint }),
  });
  if (!response.ok) throw new Error(`구독 해지에 실패했습니다 (${response.status})`);
  const removed = await subscription.unsubscribe();
  if (!removed) throw new Error("브라우저 구독 해지를 완료하지 못했습니다. 다시 시도해 주세요.");
}
