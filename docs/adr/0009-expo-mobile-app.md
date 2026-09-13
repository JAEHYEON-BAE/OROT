# ADR-0009: Expo 기반 OROT 모바일 앱

- Date: 2026-09-13
- Status: Framework and hosting accepted by owner; delivery and installation-auth details proposed

## Context

The owner selected React Native + Expo + TypeScript, retaining the Mac mini and Tailscale Funnel. An iPhone 14 and local Simulator are available. Previous blueprint §8 proposed SwiftUI; no native app has been implemented.

## Accepted direction

Create apps/mobile, launch iOS first, retain Android portability, and reuse the Python API. Keep the existing web/PWA and loopback-only API/DB. Add explicit public JSON routes through the web boundary. The initial app does not depend on accounts, watchlist matching or automated collection. Existing T-033 through T-043 are remapped in both blueprints and the detailed mobile plan.

## Proposed implementation details

Use Expo Push Service with provider-aware device/delivery records, persisted tickets/receipts and unchanged WEB behavior. Anonymous installation management uses per-installation credentials rather than an embedded admin key. See MOBILE_BLUEPRINT §3–5 for the reviewable contract, abuse constraints and migration requirements. Confirm these details before T-040/T-041 implementation; this does not block T-033 UI and read-only API work.

Alternatives: direct APNs/FCM offers more control but two provider implementations; two separate native apps increase maintenance; a WebView wrapper reuses more web UI but does not meet the selected implementation direction.

## Consequences

SwiftUI, SwiftData and Swift client generation are superseded plans, not current dependencies. Native UI must still be built, and both platforms need device validation. Expo credentials and device-management secrets stay out of client bundles. Ticket acceptance is not delivery to the user. App-store builds run without Metro, while the Mac server must remain reachable.

## References

- [Detailed mobile blueprint](../MOBILE_BLUEPRINT.ko.md)
- [Korean blueprint](../BLUEPRINT.ko.md)
- [English blueprint](../BLUEPRINT.en.md)
