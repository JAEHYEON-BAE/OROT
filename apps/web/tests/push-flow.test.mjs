import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const push = await load("../lib/push.ts");
const api = await load("../lib/api.ts");
const calendar = await load("../lib/calendar.ts");
const workerSource = await readFile(new URL("../public/sw.js", import.meta.url), "utf8");

test("calendar respects KST month boundaries and rejects repeated query values", () => {
  const today = new Date("2026-08-31T15:00:00Z");
  for (const query of ["2026-09", undefined, ["2026-09", "2026-10"], "2026-13"]) {
    assert.deepEqual(calendar.calendarMonth(query, today), { year: 2026, monthIndex: 8 });
  }
});

test("network registration failure cleans up only newly created subscriptions", async (t) => {
  const oldNotification = globalThis.Notification;
  globalThis.Notification = { requestPermission: async () => "granted" };
  t.after(() => { globalThis.Notification = oldNotification; });
  for (const hasExisting of [false, true]) {
    let removed = false;
    const subscription = { toJSON: () => ({}), unsubscribe: async () => { removed = true; } };
    browser(t, subscription);
    window.atob = atob;
    const registration = { pushManager: {
      getSubscription: async () => hasExisting ? subscription : null,
      subscribe: async () => subscription,
    } };
    navigator.serviceWorker.register = async () => registration;
    navigator.serviceWorker.ready = Promise.resolve(registration);
    t.mock.method(globalThis, "fetch", async (url) => {
      if (url.endsWith("public-key")) return Response.json({ enabled: true, public_key: "YQ" });
      throw new Error("offline");
    });
    await assert.rejects(push.subscribe(), /offline/);
    assert.equal(removed, !hasExisting);
  }
});

function browser(t, subscription) {
  const old = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: {
    serviceWorker: { getRegistration: async () => ({ pushManager: {
      getSubscription: async () => subscription,
    } }) },
  } });
  t.after(() => old ? Object.defineProperty(globalThis, "navigator", old) : delete globalThis.navigator);
  const oldWindow = globalThis.window;
  globalThis.window = { PushManager: {}, Notification: {} };
  t.after(() => { globalThis.window = oldWindow; });
}

test("failed server unsubscribe preserves the browser subscription", async (t) => {
  let removed = false;
  browser(t, { endpoint: "https://push.example/a", unsubscribe: async () => { removed = true; } });
  t.mock.method(globalThis, "fetch", async () => new Response("failed", { status: 503 }));
  await assert.rejects(push.unsubscribe(), /503/);
  assert.equal(removed, false);
});

test("permission request happens before any network await", async (t) => {
  const previous = globalThis.Notification;
  const calls = [];
  globalThis.Notification = { requestPermission: () => { calls.push("permission"); return Promise.resolve("denied"); } };
  t.after(() => { globalThis.Notification = previous; });
  t.mock.method(globalThis, "fetch", async () => { calls.push("fetch"); return Response.json({}); });
  await assert.rejects(push.subscribe(), /권한/);
  assert.deepEqual(calls, ["permission"]);
});

test("calendar fetch follows every cursor", async (t) => {
  let count = 0;
  t.mock.method(globalThis, "fetch", async (url) => {
    count++;
    if (count === 1) return Response.json({ items: [{ id: 1 }], next_cursor: "next" });
    assert.ok(url.includes("cursor=next"));
    return Response.json({ items: [{ id: 2 }], next_cursor: null });
  });
  assert.deepEqual((await api.getAllReleases()).items.map(r => r.id), [1, 2]);
});

test("failed replacement registration does not retire the old endpoint", async () => {
  const handlers = {};
  const requests = [];
  const self = { addEventListener: (name, fn) => { handlers[name] = fn; } };
  vm.runInNewContext(workerSource, {
    self, URL, Uint8Array, console: { error() {} },
    fetch: async (url, options) => {
      requests.push(options?.method ?? "GET");
      return options ? { ok: false, status: 503 } : { ok: true, json: async () => ({ enabled: true }) };
    },
  });
  let finished;
  handlers.pushsubscriptionchange({
    oldSubscription: { endpoint: "old" }, newSubscription: { endpoint: "new" },
    waitUntil: (promise) => { finished = promise; },
  });
  await finished;
  assert.deepEqual(requests, ["GET", "POST"]);
});

test("broken notification URL still opens the home page", async () => {
  const handlers = {};
  let opened;
  const self = {
    location: { origin: "https://example.com" },
    addEventListener: (name, fn) => { handlers[name] = fn; },
    clients: { matchAll: async () => [], openWindow: async (url) => { opened = url; } },
  };
  vm.runInNewContext(workerSource, { self, URL, Uint8Array });
  let finished;
  handlers.notificationclick({ notification: { data: { url: "https://[broken" }, close() {} },
    waitUntil: (promise) => { finished = promise; },
  });
  await finished;
  assert.equal(opened, "https://example.com/");
});
