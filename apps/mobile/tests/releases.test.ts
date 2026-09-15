import { releases } from "./fixtures/api";
import {
  formatPreorder,
  formatSchedule,
  formatReleaseDate,
} from "../src/features/releases/display";
test("converts UTC to KST across midnight without shifting date-only values", () => {
  expect(formatPreorder("2026-09-18T15:00:00Z")).toContain("19일");
  expect(formatPreorder(null)).toBe("예약 일정 미정");
  expect(formatReleaseDate("2026-10-02")).toBe("2026년 10월 2일");
  expect(formatReleaseDate(null)).toBe("발매일 미정");
});

test("explicit schedule modes override missing dates and honor the sale deadline", () => {
  const sale = { ...releases[0], schedule_status: "ON_SALE" as const, preorder_opens_at: null, preorder_closes_at: "2026-10-01T00:00:00Z" };
  expect(formatSchedule(sale, Date.parse("2026-09-30"))).toBe("판매 중");
  expect(formatSchedule(sale, Date.parse("2026-10-02"))).toBe("판매 종료");
  expect(formatSchedule({ ...sale, until_sold_out: true, preorder_closes_at: null }, Date.parse("2027-01-01"))).toBe("판매 중");
  expect(formatSchedule({ ...sale, schedule_status: "TBA" })).toBe("발매일 미정");
});
