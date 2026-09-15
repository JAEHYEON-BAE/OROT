import {
  getFeed,
  getRelease,
  sellerUrl,
  validRelease,
} from "../src/lib/api/client";
import { feed, releases, jsonResponse } from "./fixtures/api";
beforeEach(() => {
  (global.fetch as jest.Mock).mockReset();
});
test("sort is requested from the real service contract", async () => {
  (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(feed));
  expect((await getFeed("recent")).items).toHaveLength(3);
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/mobile/v1/feed?limit=100&sort=recent"),
    expect.any(Object),
  );
});
test("rejects draft data and malformed responses", async () => {
  expect(validRelease({ ...releases[0], is_published: false })).toBe(false);
  (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ items: "bad" }));
  await expect(getFeed("imminent")).rejects.toThrow("형식");
});
test("invalid detail ID does not make a request", async () => {
  await expect(getRelease("../admin")).rejects.toMatchObject({ status: 404 });
  expect(global.fetch).not.toHaveBeenCalled();
});
test("server errors keep status, and non-JSON is rejected", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse({}, 429));
  await expect(getFeed("recent")).rejects.toMatchObject({ status: 429 });
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    headers: { get: () => "text/html" },
  });
  await expect(getFeed("recent")).rejects.toThrow("응답");
});
test("aborts stalled requests instead of loading forever", async () => {
  jest.useFakeTimers();
  (global.fetch as jest.Mock).mockImplementation(
    (_url, { signal }) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener("abort", () => reject(new Error("aborted"))),
      ),
  );
  const result = expect(getFeed("recent")).rejects.toThrow("네트워크");
  await jest.advanceTimersByTimeAsync(12000);
  await result;
  jest.useRealTimers();
});
test("seller links only allow HTTP(S) without credentials", () => {
  expect(sellerUrl("javascript:alert(1)")).toBeNull();
  expect(sellerUrl("https://user:password@example.com")).toBeNull();
  expect(sellerUrl("https://example.com/record")).toBe(
    "https://example.com/record",
  );
});
