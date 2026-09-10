"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getExistingSubscription,
  getPublicKey,
  isIos,
  isPushSupported,
  isStandalone,
  subscribe,
  unsubscribe,
  type PushState,
} from "@/lib/push";

/**
 * 푸시 알림 켜기/끄기 (T-117).
 *
 * 상태를 뭉뚱그리지 않고 나눈다. "구독이 안 된다" 는 사용자에게 다 같아 보이지만
 * 대응이 전부 다르다 — 지원하지 않는 브라우저, 홈 화면에 추가하지 않은 iOS,
 * 사용자가 차단한 권한, 서버에 키가 없는 경우. 하나로 묶으면 아무도 못 고친다.
 */
export default function PushToggle() {
  const [state, setState] = useState<PushState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [needsHomeScreen, setNeedsHomeScreen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      // iOS 는 홈 화면에 추가하기 전에는 PushManager 자체가 없다.
      // 그냥 "지원 안 함"이라고 하면 방법이 있는데도 포기하게 된다.
      if (!isPushSupported()) {
        if (!cancelled) {
          setNeedsHomeScreen(isIos() && !isStandalone());
          setState("unsupported");
        }
        return;
      }
      try {
        const { enabled } = await getPublicKey();
        if (cancelled) return;
        if (!enabled) {
          setState("server-disabled");
          return;
        }
        if (Notification.permission === "denied") {
          setState("denied");
          return;
        }
        const existing = await getExistingSubscription();
        if (!cancelled) setState(existing ? "on" : "off");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setState("off");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      if (state === "on") {
        await unsubscribe();
        setState("off");
      } else {
        await subscribe();
        setState("on");
      }
    } catch (err) {
      // 권한을 거부하면 브라우저는 같은 출처에서 다시 물어보지 않는다.
      // 버튼만 원래대로 돌려놓으면 사용자가 계속 눌러 보게 된다.
      if (typeof Notification !== "undefined" && Notification.permission === "denied") {
        setState("denied");
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [state]);

  return (
    <section className="mt-7">
      <h2 className="font-medium">푸시 알림</h2>
      <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
        예약 시작 <strong>24시간 전</strong>과 <strong>시작하는 순간</strong>에 기기로 바로
        알려 줍니다. 계정이 필요 없습니다.
      </p>

      {state === "loading" && (
        <p className="mt-3 text-sm text-neutral-500">확인 중…</p>
      )}

      {state === "unsupported" && (
        <div className="mt-3 rounded border border-neutral-200 px-3 py-3 text-sm dark:border-neutral-800">
          {needsHomeScreen ? (
            <>
              <p className="font-medium">아이폰은 홈 화면에 추가해야 알림을 받을 수 있습니다.</p>
              <p className="mt-1 text-neutral-600 dark:text-neutral-400">
                Safari 아래쪽 공유 버튼 <span aria-hidden>⎋</span> → <strong>홈 화면에 추가</strong>{" "}
                → 홈 화면의 아이콘으로 다시 열어 주세요. iOS 16.4 이상이 필요합니다.
              </p>
            </>
          ) : (
            <p className="text-neutral-600 dark:text-neutral-400">
              이 브라우저는 웹 푸시를 지원하지 않습니다. 위의 캘린더 구독을 이용해 주세요.
            </p>
          )}
        </div>
      )}

      {state === "server-disabled" && (
        <p className="mt-3 text-sm text-neutral-500">
          서버에 푸시가 설정되어 있지 않습니다. 캘린더나 RSS 로 구독해 주세요.
        </p>
      )}

      {state === "denied" && (
        <div className="mt-3 rounded border border-neutral-200 px-3 py-3 text-sm dark:border-neutral-800">
          <p className="font-medium">알림이 차단되어 있습니다.</p>
          <p className="mt-1 text-neutral-600 dark:text-neutral-400">
            브라우저 주소창의 자물쇠 아이콘에서 이 사이트의 알림을 <strong>허용</strong>으로
            바꾼 뒤 새로고침해 주세요. 페이지에서는 다시 물어볼 수 없습니다.
          </p>
        </div>
      )}

      {(state === "on" || state === "off") && (
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            disabled={busy}
            className={
              state === "on"
                ? "rounded border border-neutral-300 px-4 py-2 text-sm disabled:opacity-50 dark:border-neutral-700"
                : "rounded bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
            }
          >
            {busy ? "처리 중…" : state === "on" ? "알림 끄기" : "알림 켜기"}
          </button>
          {state === "on" && (
            <span className="text-sm text-green-700 dark:text-green-500">
              이 기기에서 알림을 받는 중입니다.
            </span>
          )}
        </div>
      )}

      {error && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
