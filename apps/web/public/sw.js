/**
 * Vinyl Radar 서비스워커 — 푸시 수신과 알림 클릭 처리만 한다 (T-117, ADR-0006).
 *
 * 오프라인 캐싱은 하지 않는다. 캐시된 목록이 보이면 "예약 시작을 놓치지 않게" 라는
 * 약속과 어긋난다 — 지난 일정이 남아 있는 화면은 없는 것만 못하다.
 *
 * 페이로드 키는 서버의 `vinyl_core.notifications.build_payload` 가 만든다.
 * 여기서 읽는 이름과 서버가 보내는 이름이 어긋나면 알림이 조용히 기본 문구로
 * 바뀌므로, `apps/api/tests/test_edge_cases.py` 의 계약 시험이 양쪽을 맞춰 둔다.
 */

const ICON = "/icon-192.png";
const BADGE = "/icon-192.png";

// 페이로드가 없거나 깨졌을 때 보여 줄 내용.
// **무조건 알림을 띄워야 한다** — 아래 주석 참조.
const FALLBACK = {
  title: "Vinyl Radar",
  body: "새 일정이 있습니다. 눌러서 확인하세요.",
  url: "/",
  tag: "vinyl-radar",
};

self.addEventListener("install", () => {
  // 새 서비스워커를 즉시 활성화한다. 기다리면 알림 로직 수정이
  // 모든 탭을 닫을 때까지 반영되지 않는다.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// 아무것도 하지 않는 fetch 핸들러.
// respondWith 를 부르지 않으므로 브라우저는 평소대로 네트워크를 탄다.
// 크롬이 설치 가능(PWA) 판정에 fetch 핸들러의 존재를 요구해서 남겨 둔다.
self.addEventListener("fetch", () => {});

function parsePayload(event) {
  if (!event.data) return FALLBACK;
  try {
    const data = event.data.json();
    return {
      title: typeof data.title === "string" && data.title ? data.title : FALLBACK.title,
      body: typeof data.body === "string" && data.body ? data.body : FALLBACK.body,
      url: typeof data.url === "string" && data.url ? data.url : FALLBACK.url,
      tag: typeof data.tag === "string" && data.tag ? data.tag : FALLBACK.tag,
    };
  } catch (err) {
    // 여기서 던지면 알림이 안 뜬다. 형식이 틀린 것은 우리 잘못이지
    // 사용자가 알림을 못 받을 이유는 아니다.
    console.error("[sw] 푸시 페이로드를 읽지 못했습니다", err);
    return FALLBACK;
  }
}

self.addEventListener("push", (event) => {
  const data = parsePayload(event);

  // **반드시 알림을 띄운다.** userVisibleOnly 로 구독했기 때문에, 푸시를 받고도
  // 알림을 띄우지 않으면 브라우저가 "사이트가 백그라운드에서 갱신됨" 같은
  // 대체 알림을 대신 띄우고, 반복되면 푸시 권한 자체를 회수한다.
  //
  // waitUntil 없이 부르면 showNotification 이 끝나기 전에 워커가 종료될 수 있다.
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: ICON,
      badge: BADGE,
      // 같은 발매의 알림을 하나로 묶는다.
      tag: data.tag,
      // 묶인 알림은 기본적으로 **소리 없이** 교체된다.
      // 그러면 '예약 임박' 위에 덮인 '예약 시작'을 사용자가 못 본다 —
      // 이 제품이 유일하게 놓치면 안 되는 순간이다. 그래서 다시 알린다.
      renotify: true,
      // 예약 시작은 몇 분 안에 매진되기도 한다. 사용자가 직접 닫을 때까지 남긴다.
      requireInteraction: true,
      data: { url: data.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin);

  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      // 이미 열려 있는 탭이 있으면 새 탭을 만들지 않는다.
      for (const client of windows) {
        if (new URL(client.url).origin !== target.origin) continue;
        await client.focus();
        if ("navigate" in client && client.url !== target.href) {
          await client.navigate(target.href);
        }
        return;
      }
      await self.clients.openWindow(target.href);
    })(),
  );
});

/**
 * base64url VAPID 공개키를 바이트 배열로.
 *
 * 규격상 문자열을 그대로 넘겨도 되지만 받아들이지 않는 브라우저가 있어
 * 바이트로 바꿔 넘긴다. `lib/push.ts` 에 같은 함수가 있다 —
 * 서비스워커는 앱 번들을 임포트할 수 없어 중복이 불가피하다.
 */
function urlBase64ToUint8Array(base64) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = self.atob(padded);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

/**
 * 브라우저가 구독을 교체할 때 불린다 (키 만료·저장소 정리 등).
 *
 * 여기서 다시 등록하지 않으면 **구독이 조용히 죽는다.** 사용자는 구독 중이라고
 * 믿는데 알림만 오지 않는 상태가 되며, 알아챌 방법이 없다.
 */
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    (async () => {
      const oldEndpoint = event.oldSubscription?.endpoint;
      try {
        const res = await fetch("/api/push/public-key");
        const { public_key: publicKey, enabled } = await res.json();
        if (!enabled) return;

        const fresh =
          event.newSubscription ||
          (await self.registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
          }));

        await fetch("/api/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fresh.toJSON ? fresh.toJSON() : fresh),
        });

        // 죽은 엔드포인트를 남겨 두면 발송기가 매 주기 그쪽으로 요청을 보낸다.
        if (oldEndpoint && oldEndpoint !== fresh.endpoint) {
          await fetch("/api/push/subscribe", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ endpoint: oldEndpoint }),
          });
        }
      } catch (err) {
        console.error("[sw] 구독 갱신 실패", err);
      }
    })(),
  );
});
