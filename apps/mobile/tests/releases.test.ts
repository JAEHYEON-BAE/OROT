import { formatPreorder, formatReleaseDate } from "../src/features/releases/display";
import {
  demoReleases,
  findDemoRelease,
  sortDemoReleases,
} from "./fixtures/demo";

test("unknown dates stay last, recent sort does not mutate source fixtures", () => {
  expect(sortDemoReleases("imminent").map((r) => r.id)).toEqual([1, 2, 3]);
  expect(sortDemoReleases("recent").map((r) => r.id)).toEqual([2, 1, 3]);
  expect(demoReleases.map((r) => r.id)).toEqual([1, 2, 3]);
});
test.each(["1junk", "01", "-1", "999", undefined])(
  "rejects missing or ambiguous route id %s",
  (id) => {
    expect(findDemoRelease(id)).toBeUndefined();
  },
);
test("converts UTC to KST across midnight without shifting date-only values", () => {
  expect(formatPreorder("2026-09-18T15:00:00Z")).toContain("19일");
  expect(formatPreorder(null)).toBe("예약 일정 미정");
  expect(formatReleaseDate("2026-10-02")).toBe("2026년 10월 2일");
  expect(formatReleaseDate(null)).toBe("발매일 미정");
});

