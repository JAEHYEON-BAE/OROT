import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/feed-display.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { feedDisplay } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const release = {
  preorder_opens_at: "2026-09-11T13:00:00+09:00",
  preorder_closes_at: "2026-09-13T18:00:00+09:00",
  release_date: null,
};

test("future preorder never claims it has started", () => {
  const display = feedDisplay(release, Date.parse("2026-09-10T14:00:00+09:00"));
  assert.equal(display.status, "예약 예정");
  assert.equal(display.at, release.preorder_opens_at);
});
test("opening and closing boundaries are inclusive", () => {
  const opening = Date.parse(release.preorder_opens_at);
  const closing = Date.parse(release.preorder_closes_at);
  assert.equal(feedDisplay(release, opening - 1).status, "예약 예정");
  assert.equal(feedDisplay(release, opening).status, "예약 진행 중");
  assert.equal(feedDisplay(release, closing - 1).status, "예약 진행 중");
  assert.equal(feedDisplay(release, closing).status, "예약 마감");
});
test("missing preorder falls back to release date at KST midnight", () => {
  const r = { ...release, preorder_opens_at: null, release_date: "2026-09-11" };
  assert.equal(feedDisplay(r, Date.parse("2026-09-10T14:59:59Z")).status, "발매 예정");
  assert.equal(feedDisplay(r, Date.parse("2026-09-10T15:00:00Z")).status, "발매됨");
  assert.equal(feedDisplay(r, Date.now()).at, "2026-09-11");
});
test("unknown dates never display an event or registration timestamp", () => {
  const r = { ...release, preorder_opens_at: null };
  assert.equal(feedDisplay(r, Date.now()).status, "일정 미정");
  assert.equal(feedDisplay(r, Date.now()).at, null);
});


test("explicit sale mode handles deadline and TBA", () => {
  const sale = { ...release, preorder_opens_at: null, schedule_status: "ON_SALE" };
  assert.equal(feedDisplay(sale, Date.parse("2026-09-12")).status, "판매 중");
  assert.equal(feedDisplay(sale, Date.parse("2026-09-14")).status, "판매 종료");
  assert.equal(feedDisplay({ ...sale, preorder_closes_at: null, until_sold_out: true }, Date.parse("2027-01-01")).status, "판매 중");
  assert.equal(feedDisplay({ ...sale, schedule_status: "TBA" }, Date.now()).status, "발매일 미정");
});
