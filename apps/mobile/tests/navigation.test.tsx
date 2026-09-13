import { fireEvent, screen } from '@testing-library/react-native';
import { renderRouter } from 'expo-router/testing-library';
import Feed from '../src/app/(tabs)/index';
import Detail from '../src/app/releases/[id]';
import Settings from '../src/app/(tabs)/settings';
import { feed, releases, jsonResponse } from './fixtures/api';

beforeEach(() => {
  (global.fetch as jest.Mock).mockReset().mockImplementation(async (url: string) => {
    if (url.includes('/v1/feed?')) return jsonResponse(feed);
    if (url.endsWith('/v1/releases/2')) return jsonResponse(releases[1]);
    return jsonResponse({}, 404);
  });
});
test('server feed opens a detail response, without falling back to demo data', async () => {
  const router = renderRouter({ index: Feed, 'releases/[id]': Detail }, { initialUrl: '/' });
  fireEvent.press(await screen.findByRole('link', { name: '밤의 가장자리, 작은 파동, 상세 보기' }));
  expect(await screen.findByText('2026년 10월 16일')).toBeTruthy();
  expect(router.getPathname()).toBe('/releases/2');
  expect(screen.getByText('테스트 판매처 ↗')).toBeTruthy();
  expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/mobile/v1/releases/2'), expect.any(Object));
});
test('404 detail has a recovery path', async () => {
  renderRouter({ index: Feed, 'releases/[id]': Detail }, { initialUrl: '/releases/999' });
  expect(await screen.findByText('일정을 찾을 수 없습니다.')).toBeTruthy();
  expect(screen.getByText('발매 목록으로 돌아가기')).toBeTruthy();
});
test('feed failures show retry and never demo records', async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse({}, 502)).mockResolvedValue(jsonResponse(feed));
  renderRouter({ index: Feed }, { initialUrl: '/' });
  fireEvent.press(await screen.findByRole('button', { name: '다시 불러오기' }));
  expect(await screen.findByText('느린 오후')).toBeTruthy();
});
test('settings does not pretend mobile push is enabled', () => {
  renderRouter({ settings: Settings }, { initialUrl: '/settings' });
  expect(screen.getByText(/모바일 알림은 준비 중/)).toBeTruthy();
  expect(screen.queryByRole('switch')).toBeNull();
});
