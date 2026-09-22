# ADR-0006: 알림 채널 — Web Push 우선, iOS 네이티브는 이후

- **상태**: **Accepted** — 2026-09-07 결정
- **관련**: 블루프린트 §2.1, §4.2, §5.2, §8.3, §10(M2) / ADR-0005
- **대체 관계**: 기존 M2 의 T-114(이메일 구독)를 **Web Push 로 교체**한다.
  §8.3 의 APNs 계획은 폐기하지 않고 **뒤로 미룬다**

---

## 1. 결정

발송 채널을 **Web Push(PWA)** 로 먼저 만든다. iOS 네이티브(APNs)는 그 뒤에 더한다.
이메일은 만들지 않는다.

```
NotificationDispatcher
 ├─ WebPushSender   ← 지금 (무료, 앱 불필요)
 ├─ ApnsSender      ← 이후 (iOS 앱 배포 시)
 └─ FcmSender       ← 필요해지면
```

## 2. 선택지 비교

| | 연 비용 | 앱 개발 | iOS | Android | 심사 |
|---|---|---|---|---|---|
| **Web Push (PWA)** | **0원** | **불필요** | 16.4+ · **홈 화면 추가 필요** | 됨 | 없음 |
| FCM (Android 네이티브) | 0원 | Kotlin 앱 | ✗ | 됨 | Play 심사 |
| APNs (iOS 네이티브) | **$99/년** | Swift 앱 | 됨 | ✗ | App Store 심사 |
| 이메일 | 0~ | 불필요 | 됨 | 됨 | 없음 |

## 3. 근거

### (a) 지금 있는 것에 얹으면 된다

Next.js 웹 앱이 이미 있다. 매니페스트와 서비스워커를 더하면 PWA 가 되고,
브라우저가 주는 구독 정보를 저장하면 발송이 성립한다. **새 앱을 만들 필요가 없다.**

### (b) 이 프로젝트가 지금까지 택해 온 방식과 같다

계정 시스템 없이 RSS·iCalendar 로 핵심 가치를 먼저 배송했다 (ADR-0005 §4.3).
같은 논리로 **$99 와 앱 심사 없이 푸시를 먼저 검증**한다.
사용자가 실제로 푸시를 쓰는지 확인한 뒤 네이티브에 투자한다.

### (c) 스키마가 이미 이 경로를 열어 두었다

`device_tokens.platform` 이 `'IOS' | 'WEB'` 이다. **`WEB` 이 곧 Web Push 자리다.**

### (d) 이메일을 만들지 않는 이유

프로젝트 소유자가 필요를 느끼지 않는다고 밝혔다. 발송 서비스 계정·도메인 인증·
스팸 대응이라는 별도 운영 부담이 따르는데, 지금 얻는 것이 없다.

## 4. 감수하는 것 — 정직하게

**iOS 에 마찰이 있다.** Safari 의 Web Push 는 16.4+ 에서만 동작하고,
사용자가 **공유 → 홈 화면에 추가**를 해야 알림 권한을 요청할 수 있다.
그냥 사파리 탭으로 열어 두면 알림이 오지 않는다.

한정반을 놓치지 않으려는 사용자라면 그 정도 설정은 감수할 만하다고 보지만,
"설치 없이 바로"는 아니다. 안드로이드에는 이 제약이 없다.

**도달률이 네이티브보다 낮을 수 있다.** iOS Web Push 는 백그라운드 제약이 더 크다.
**실측 전에는 단정하지 않는다** — M2 이후 실제 발송 성공률을 지표로 확인한다.

외부 배포 시 iOS 사용자 비중이 크면 이것이 병목이 된다.
그때가 §8.3 의 APNs 경로를 여는 시점이다.

## 5. 스키마 변경

### 5.1 `device_tokens` 확장

```sql
ALTER TABLE device_tokens
  ALTER COLUMN user_id DROP NOT NULL,   -- 익명 구독 (계정 시스템은 M4)
  ADD COLUMN p256dh          TEXT,      -- Web Push 구독 공개키
  ADD COLUMN auth            TEXT,      -- Web Push 인증 시크릿
  ADD COLUMN created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN last_success_at TIMESTAMPTZ,
  ADD COLUMN failure_count   INT NOT NULL DEFAULT 0;
```

- `user_id` 를 NULL 허용으로 바꾼다. **Web Push 는 구독 자체가 식별자**라 계정이 필요 없다.
  M4 에서 계정이 생기면 익명 구독을 계정에 붙일 수 있다
- `token` 은 플랫폼마다 의미가 다르다 — `WEB` 이면 푸시 엔드포인트 URL,
  `IOS` 면 APNs 디바이스 토큰. `UNIQUE (platform, token)` 이 중복 구독을 막는다
- `p256dh` / `auth` 는 Web Push 암호화(RFC 8291)에 필요하다. `IOS` 에는 NULL

### 5.2 신규 `notification_deliveries`

**발송 멱등성의 근거다.** 어떤 이벤트를 어떤 구독에 보냈는지 기록한다.

```sql
CREATE TABLE notification_deliveries (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES listing_events(id) ON DELETE CASCADE,
    device_token_id BIGINT NOT NULL REFERENCES device_tokens(id)  ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','SENT','FAILED','EXPIRED')),
    attempts        INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, device_token_id)   -- 같은 이벤트/기기의 배송 행 중복을 막는다
);
CREATE INDEX ON notification_deliveries (status, created_at);
```

**2026-09-11 구현 정정:** UNIQUE는 배송 행의 중복을 막는다. 현재 스케줄러는 DB 잠금으로
중복 실행을 막고 SENT를 재처리하지 않는다. 그러나 외부 푸시 전송과 DB 커밋은 원자적이지 않아
전송 성공 직후 종료되거나 응답이 유실되면 재전송 가능성이 있다. exactly-once 보장은 아니다.
SENT는 푸시 서비스 수락이며 실제 화면 표시 확인이 아니다.

`EXPIRED`는 만료 구독뿐 아니라 공개 취소·구독 해지·이벤트 무효화·발송 기한 초과도 포함한다.
Web Push의 404/410은 구독도 비활성화한다. FAILED는 최대 3회 시도하며 배송 생성 1분·5분
이후 재시도할 수 있다. 재시도 소진은 로그에 남지만 외부 운영자 알림은 아직 없다.

## 6. API

```
POST   /v1/push/subscribe      구독 등록 (인증 불필요)
DELETE /v1/push/subscribe      구독 해지
GET    /v1/push/public-key     VAPID 공개키 (브라우저가 구독할 때 필요)
```

블루프린트 §5.2 의 `POST /v1/devices`(APNs 토큰 등록)는 iOS 앱을 만들 때 그대로 쓴다.

## 7. 백로그 재편 (M2)

| ID | 작업 | 완료 조건 |
|---|---|---|
| ~~T-114~~ | ~~이메일 구독~~ | **폐기** — ADR-0006 |
| T-114 | Web Push 구독 (VAPID 키, 구독/해지 API, 스키마 확장) | 브라우저가 구독하고 DB 에 저장됨 |
| T-115 | 발송기 + 멱등 배송 (`notification_deliveries`) | **스케줄러 재기동 후 중복 발송 0건** |
| T-116 | 재시도 + 만료 구독 정리 + 무음 실패 알림 | 의도적 실패 시 운영자 알림, 410 이면 구독 비활성화 |
| T-117 | 웹 구독 UI (PWA 매니페스트 + 서비스워커) | 실제 기기에서 알림 수신 |

> **T-113 정정**: 기존 T-113 은 "발송 멱등성"이었으나, 검증한 것은
> **이벤트 생성 멱등성**이었다. 발송 자체의 멱등성은 `notification_deliveries` 가
> 생겨야 성립하므로 **T-115 에서 완료**한다.

## 8. 재검토 조건

- iOS 사용자 비중이 크고 홈 화면 추가 전환율이 낮을 때 → §8.3 APNs 경로
- 발송 성공률이 목표(§1.3 의 99%)에 못 미칠 때 → 채널 추가 검토

## 2026-09-15 발송 트랜잭션 보완

스케줄러는 세션 advisory lock을 유지하면서 계획을 먼저 커밋하고, HTTP 전송 이후
결과를 건별 커밋한다. HTTP 중 DB 트랜잭션을 유지하지 않는다. 최대 5개 병렬,
동일 구독은 순차이며 45초 이후 새 작업을 시작하지 않는다. 500건 상한은 유지한다.
UNIQUE 제약과 상태 전이는 유지하지만, 전송 수락과 결과 커밋 사이의 중복 가능성은
남는다. 이미 커밋한 배치 앞부분 전체가 롤백되지는 않는다. 새 runtime 검증은
`integration_dispatch.py`이며 실제 실행 여부는 [검토 결과](../issue-review-20260915-resolution.md)를 따른다.
