import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../lib/mobile-read.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { mobileRead } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const request = (query = '', method = 'GET') => new Request(`https://orot.test/api/mobile/v1/feed${query}`, { method, headers: { 'X-Admin-Key': 'never-forward', Cookie: 'private', Authorization: 'private' } });
test('fixed public path preserves query and drops client credentials', async t => {
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, 'http://localhost:8000/v1/feed?sort=recent&limit=10');
    assert.deepEqual(init.headers, { Accept: 'application/json' });
    assert.equal(init.redirect, 'error'); assert.equal(init.cache, 'no-store');
    return Response.json({ items: [], generated_at: 'test' });
  });
  const res = await mobileRead(request('?sort=recent&limit=10'), 'feed');
  assert.equal(res.status, 200); assert.equal(res.headers.get('cache-control'), 'no-store');
});
test('unknown/duplicate queries, invalid ids and writes never reach upstream', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('unexpected'); });
  for (const query of ['?url=http://private', '?sort=recent&sort=imminent', '?limit=101', '?limit=-1']) assert.equal((await mobileRead(request(query), 'feed')).status, 400);
  assert.equal((await mobileRead(request(), 'detail', '../admin')).status, 400);
  assert.equal((await mobileRead(request('', 'POST'), 'feed')).status, 405);
  assert.equal(mock.mock.callCount(), 0);
});
test('detail upstream 404 and retry information preserved without secret headers', async t => {
  t.mock.method(globalThis, 'fetch', async url => {
    assert.ok(url.endsWith('/v1/releases/999'));
    return Response.json({ detail: 'not found' }, { status: 404, headers: { 'Retry-After': '10', 'Set-Cookie': 'secret' } });
  });
  const res = await mobileRead(request(), 'detail', '999');
  assert.equal(res.status, 404); assert.equal(res.headers.get('Retry-After'), '10'); assert.equal(res.headers.get('Set-Cookie'), null);
});
test('HTML, failed and oversized upstream responses are bounded JSON errors', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => new Response('<html>failure</html>'));
  assert.equal((await mobileRead(request(), 'feed')).status, 502);
  mock.mock.mockImplementation(async () => new Response('x'.repeat(4 * 1024 * 1024 + 1), { headers: { 'content-type': 'application/json' } }));
  assert.equal((await mobileRead(request(), 'feed')).status, 502);
  mock.mock.mockImplementation(async () => { throw new Error('internal secret'); });
  const res = await mobileRead(request(), 'feed'); assert.equal(res.status, 502); assert.ok(!(await res.text()).includes('secret'));
});
