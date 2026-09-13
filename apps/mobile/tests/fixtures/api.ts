import { demoReleases } from './demo';
import type { Release, FeedPage } from '../../src/lib/api/client';
export const releases: Release[] = demoReleases.map(({ color: _color, updated_at: _updated, ...r }) => ({ ...r, curation: 'MANUAL', is_limited: false, is_published: true, links: [{ id: r.id, shop_name: '테스트 판매처', url: 'https://example.com/record', price_krw: 45000 }] }));
export const feed: FeedPage = { generated_at: '2026-09-13T00:00:00Z', items: releases.map(release => ({ kind: 'UPCOMING', at: '2026-09-18T05:00:00Z', event_type: null, release })) };
export function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, headers: { get: () => 'application/json' }, json: async () => body } as unknown as Response;
}
