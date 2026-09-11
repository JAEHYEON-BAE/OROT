"""운영자 등록 화면 — 최소 HTML 폼 (T-109, ADR-0005).

의존성을 늘리지 않으려고 템플릿 엔진 없이 문자열로 렌더링한다.
화면은 하나뿐이고 필드도 고정이라 이 정도면 충분하다.

**인증**: 브라우저에서 헤더를 붙일 수 없으므로, 폼은 입력받은 키를
`fetch()` 의 `X-Admin-Key` 헤더로 넣어 기존 관리 API 를 호출한다.
키는 `sessionStorage` 에만 두고 서버로 저장하지 않는다.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-ui"], include_in_schema=False)

_PAGE = """<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>발매 일정 등록</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
         max-width: 46rem; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.3rem; margin-bottom: .2rem; }
  p.sub { margin-top: 0; opacity: .7; font-size: .9rem; }
  fieldset { border: 1px solid #8884; border-radius: 8px; margin: 1rem 0; padding: 1rem; }
  legend { padding: 0 .4rem; font-weight: 600; }
  label { display: block; margin: .6rem 0 .15rem; font-size: .87rem; opacity: .85; }
  input, textarea, select { width: 100%; padding: .45rem .55rem; font: inherit;
         border: 1px solid #8886; border-radius: 6px; background: transparent; color: inherit; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }
  .check { display: flex; align-items: center; gap: .4rem; margin-top: .8rem; }
  .check input { width: auto; }
  button { font: inherit; padding: .5rem 1rem; border-radius: 6px; border: 1px solid #8886;
           background: #2a6; color: #fff; cursor: pointer; }
  button.secondary { background: transparent; color: inherit; }
  .hint { font-size: .8rem; opacity: .6; margin-top: .15rem; }
  #out { white-space: pre-wrap; padding: .8rem; border-radius: 6px; margin-top: 1rem;
         font-size: .85rem; display: none; }
  #out.ok { display: block; background: #2a62; border: 1px solid #2a68; }
  #out.err { display: block; background: #d442; border: 1px solid #d448; }
  table { width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .6rem; }
  th, td { text-align: left; padding: .35rem .4rem; border-bottom: 1px solid #8883; }
  .draft { opacity: .55; }
  .link-row { display: grid; grid-template-columns: 1fr 1.6fr .7fr auto; gap: .5rem;
              align-items: end; margin-bottom: .5rem; }
  .link-row button { background: transparent; color: inherit; padding: .45rem .6rem; }
  td button { font-size: .8rem; padding: .2rem .5rem; margin-right: .25rem;
              background: transparent; color: inherit; }
  td button.pub { background: #2a6; color: #fff; border-color: #2a6; }
  body.editing { background: #2a60a; }
  body.editing #h1::after { content: " — 수정 중"; color: #2a6; }
  .link-row label { margin-top: 0; }
  @media (max-width: 640px) { .link-row { grid-template-columns: 1fr; } }
  .topbar { display:flex; align-items:center; gap:.75rem; margin-bottom:.5rem; }
  .topbar .hint { margin:0; }
  .linkish { background:none; border:0; padding:0; color:#0645ad; cursor:pointer;
             text-decoration:underline; font-size:.85rem; width:auto; }
  #loginOut { margin-left:.6rem; font-size:.85rem; }
  #loginOut.err { color:#b00020; }
</style>

<!-- 로그인 화면. 키가 확인되기 전에는 이것만 보인다 (T-134). -->
<section id="login">
  <h1>운영자 로그인</h1>
  <p class="sub">Vinyl Radar 관리 화면입니다.</p>
  <form id="loginForm">
    <fieldset>
      <legend>운영자 키</legend>
      <input id="key" type="password" placeholder="ADMIN_API_KEY"
             autocomplete="current-password" required>
      <p class="hint">이 브라우저 탭에만 보관되며 서버로 저장되지 않습니다.</p>
      <button type="submit" id="loginBtn">로그인</button>
      <span id="loginOut"></span>
    </fieldset>
  </form>
</section>

<section id="app" hidden>
<div class="topbar">
  <span class="hint" id="who">운영자로 로그인됨</span>
  <button type="button" id="logout" class="linkish">로그아웃</button>
</div>

<h1 id="h1">발매 일정 등록</h1>
<p class="sub" id="sub">등록하면 <strong>초안</strong>으로 저장됩니다.
  공개해야 사용자에게 보입니다.</p>

<form id="f">
  <fieldset>
    <legend>앨범</legend>
    <div class="row">
      <div><label>아티스트</label><input name="artist_name" placeholder="실리카겔"></div>
      <div><label>앨범명 *</label><input name="title" required placeholder="Machine Boy"></div>
    </div>
    <div class="row">
      <div><label>레이블</label><input name="label" placeholder="Magic Strawberry Sound"></div>
      <div><label>포맷</label><input name="format" placeholder="2LP"></div>
    </div>
    <div class="row">
      <div><label>바리언트</label><input name="variant" placeholder="Clear Vinyl">
        <p class="hint">색상·한정 표기. <strong>다르면 다른 발매로 취급합니다.</strong></p></div>
      <div><label>커버 이미지 URL</label><input name="cover_url" placeholder="https://..."></div>
    </div>
    <div class="check"><input type="checkbox" name="is_limited" id="lim"><label for="lim"
      style="margin:0">한정반</label></div>
  </fieldset>

  <fieldset>
    <legend>일정</legend>
    <div class="row">
      <div><label>예약 시작</label><input name="preorder_opens_at" type="datetime-local">
        <p class="hint">알림이 발송되는 시각입니다. 한국 시간(KST)으로 입력하세요.</p></div>
      <div><label>예약 마감</label><input name="preorder_closes_at" type="datetime-local">
        <p class="hint">모르면 비워 두세요.</p></div>
    </div>
    <label>발매일</label><input name="release_date" type="date">
  </fieldset>

  <fieldset>
    <legend>구매처 (선택 · 여러 곳 등록 가능)</legend>
    <div id="links"></div>
    <button type="button" class="secondary" id="addLink">+ 판매처 추가</button>
    <p class="hint">같은 URL 을 두 번 넣으면 하나로 합쳐집니다.</p>
  </fieldset>

  <fieldset>
    <legend>메모 (비공개)</legend>
    <textarea name="notes" rows="2" placeholder="300장 한정, 인스타 공지 확인"></textarea>
  </fieldset>

  <button type="submit" id="submitBtn">초안으로 등록</button>
  <button type="button" class="secondary" id="cancelEdit" style="display:none">수정 취소</button>
  <button type="button" class="secondary" id="reload">목록 새로고침</button>
</form>

<div id="out"></div>

<h2 style="font-size:1.05rem;margin-top:2rem">등록된 일정</h2>
<table id="list"><thead><tr>
  <th>ID</th><th>아티스트 / 앨범</th><th>예약 시작</th><th>구매처</th><th>상태</th><th>동작</th>
</tr></thead><tbody></tbody></table>
</section>

<script>
const $ = (s) => document.querySelector(s);

// ── 로그인 (T-134) ──────────────────────────────────────────
// 키는 여전히 `X-Admin-Key` 헤더로만 나간다. 바뀐 것은 **화면의 흐름**뿐이다 —
// 키 칸이 페이지마다 떠 있으면 매번 다시 넣어야 하는 것처럼 보이고,
// 비어 있는 채로 등록을 눌러 401 을 받는 일이 반복된다.
//
// 세션 저장소를 쓴다. 탭을 닫으면 사라지므로 공용 기기에 남지 않는다.
let adminKey = sessionStorage.getItem("adminKey") || "";
const key = () => adminKey;

function enterApp() {
  $("#login").hidden = true;
  $("#app").hidden = false;
}

function leaveApp(message) {
  adminKey = "";
  sessionStorage.removeItem("adminKey");
  $("#app").hidden = true;
  $("#login").hidden = false;
  $("#key").value = "";
  loginMessage(message || "");
  $("#key").focus();
}

function loginMessage(text) {
  const o = $("#loginOut");
  o.textContent = text;
  o.className = text ? "err" : "";
}

/** 키가 맞는지 **서버에 물어본다.** 형식만 보고 통과시키면 첫 등록에서야 실패한다. */
async function verifyKey(candidate) {
  const res = await fetch("/admin/releases", { headers: { "X-Admin-Key": candidate } });
  if (res.ok) return true;
  if (res.status === 401) return false;
  throw new Error(`${res.status}`);
}

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const candidate = $("#key").value.trim();
  if (!candidate) return;
  const btn = $("#loginBtn");
  btn.disabled = true;
  loginMessage("");
  try {
    if (await verifyKey(candidate)) {
      adminKey = candidate;
      sessionStorage.setItem("adminKey", adminKey);
      $("#key").value = "";
      enterApp();
      await load();
    } else {
      loginMessage("키가 올바르지 않습니다.");
    }
  } catch (err) {
    loginMessage(`서버에 연결하지 못했습니다 (${err.message}).`);
  } finally {
    btn.disabled = false;
  }
});

$("#logout").addEventListener("click", () => leaveApp(""));

function show(msg, ok) {
  const o = $("#out");
  o.textContent = msg;
  o.className = ok ? "ok" : "err";
}

// datetime-local 은 타임존이 없다. 서버가 naive 를 거부하므로 KST 오프셋을 붙인다.
function toKst(v) { return v ? v + ":00+09:00" : null; }

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": key(),
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  if (res.status === 401) {
    // 서버에서 키가 바뀐 경우다. 오류만 띄우면 왜 안 되는지 알 수 없다.
    leaveApp("세션이 만료되었습니다. 다시 로그인하십시오.");
    throw new Error("401");
  }
  if (!res.ok) throw new Error(`${res.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

// ── 상태 ────────────────────────────────────────────────────
// null 이면 신규 등록, 숫자면 그 id 를 수정하는 중이다.
let editingId = null;

// ── 구매처 행 ───────────────────────────────────────────────
// 기존 링크는 data-link-id 를 달아 둔다. 저장할 때 무엇이 지워지고
// 무엇이 새로 생겼는지 비교하는 기준이 된다.
function addLinkRow(values = {}) {
  const row = document.createElement("div");
  row.className = "link-row";
  row.innerHTML = `
    <div><label>판매처</label><input class="l-shop" placeholder="김밥레코즈"></div>
    <div><label>상품 URL</label><input class="l-url" placeholder="https://..."></div>
    <div><label>가격</label><input class="l-price" type="number" min="0" step="1"
         placeholder="52000"></div>
    <button type="button" title="삭제">✕</button>`;
  row.querySelector(".l-shop").value = values.shop_name || "";
  row.querySelector(".l-url").value = values.url || "";
  row.querySelector(".l-price").value = values.price_krw ?? "";
  if (values.id) {
    row.dataset.linkId = values.id;
    row.dataset.origin = JSON.stringify({
      shop_name: values.shop_name || "",
      url: values.url || "",
      price_krw: values.price_krw ?? null,
    });
  }
  row.querySelector("button").addEventListener("click", () => {
    row.remove();
    if ($("#links").children.length === 0) addLinkRow();
  });
  $("#links").append(row);
}

function readRow(row) {
  const price = row.querySelector(".l-price").value;
  return {
    shop_name: row.querySelector(".l-shop").value.trim(),
    url: row.querySelector(".l-url").value.trim(),
    price_krw: price ? Number(price) : null,
    source_id: row.dataset.origin ? JSON.parse(row.dataset.origin).source_id : null,
  };
}

function collectLinks() {
  return [...document.querySelectorAll(".link-row")]
    .map(readRow)
    .filter((l) => l.url)
    .map((l) => ({ ...l, shop_name: l.shop_name || "판매처" }));
}

$("#addLink").addEventListener("click", () => addLinkRow());
addLinkRow();

// ── 편집 모드 ────────────────────────────────────────────────
function resetForm() {
  editingId = null;
  $("#f").reset();
  $("#links").innerHTML = "";
  addLinkRow();
  document.body.classList.remove("editing");
  $("#h1").textContent = "발매 일정 등록";
  $("#submitBtn").textContent = "초안으로 등록";
  $("#cancelEdit").style.display = "none";
}

// UTC ISO → datetime-local 이 이해하는 KST 문자열
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const kst = new Date(d.getTime() + 9 * 3600 * 1000);
  return kst.toISOString().slice(0, 16);
}

function startEdit(r) {
  editingId = r.id;
  const f = $("#f");
  const set = (name, v) => { f.elements[name].value = v ?? ""; };
  set("title", r.title);
  set("artist_name", r.artist_name);
  set("label", r.label);
  set("format", r.format);
  set("variant", r.variant);
  set("cover_url", r.cover_url);
  set("notes", r.notes);
  set("release_date", r.release_date);
  set("preorder_opens_at", toLocalInput(r.preorder_opens_at));
  set("preorder_closes_at", toLocalInput(r.preorder_closes_at));
  f.elements["is_limited"].checked = !!r.is_limited;

  $("#links").innerHTML = "";
  if (r.links.length) r.links.forEach(addLinkRow);
  else addLinkRow();

  document.body.classList.add("editing");
  $("#h1").textContent = `일정 #${r.id}`;
  $("#submitBtn").textContent = "수정 저장";
  $("#cancelEdit").style.display = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("#cancelEdit").addEventListener("click", resetForm);

// ── 저장 ────────────────────────────────────────────────────
function readForm() {
  const d = Object.fromEntries(new FormData($("#f")));
  return {
    title: d.title,
    artist_name: d.artist_name || null,
    label: d.label || null,
    format: d.format || null,
    variant: d.variant || null,
    is_limited: !!d.is_limited,
    release_date: d.release_date || null,
    preorder_opens_at: toKst(d.preorder_opens_at),
    preorder_closes_at: toKst(d.preorder_closes_at),
    cover_url: d.cover_url || null,
    notes: d.notes || null,
  };
}

$("#f").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#submitBtn").disabled) return;
  $("#submitBtn").disabled = true;
  try {
    if (editingId === null) {
      const body = { ...readForm(), links: collectLinks() };
      const r = await api("/admin/releases", {
        method: "POST",
        body: JSON.stringify(body),
      });
      show(
        `등록됨 (id=${r.id}, 구매처 ${r.links.length}곳).` +
          ` 아래에서 '공개'를 눌러야 사용자에게 보입니다.`,
        true,
      );
    } else {
      const id = editingId;
      await api(`/admin/releases/${id}`, {
        method: "PATCH", body: JSON.stringify({ ...readForm(), links: collectLinks() }),
      });
      show(`일정 #${id} 저장됨`, true);
    }
    resetForm();
    load();
  } catch (err) {
    show(String(err.message), false);
  } finally {
    $("#submitBtn").disabled = false;
  }
});

// ── 목록 ────────────────────────────────────────────────────
// **문자열로 HTML 을 만들 때는 반드시 이스케이프한다** (T-130).
// 제목·아티스트·판매처 이름은 사람이 입력한 값이라 `<img onerror=...>` 가 들어올 수
// 있고, 그러면 이 화면에서 실행된다 — 운영자 키가 sessionStorage 에 있으므로
// 여기서의 XSS 는 곧 운영자 권한 탈취다.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

async function load() {
  const fmt = (t) => (t ? new Date(t).toLocaleString("ko-KR") : "-");
  try {
    const rows = await api("/admin/releases");
    $("#list tbody").innerHTML = rows.map((r) => `
      <tr class="${r.is_published ? "" : "draft"}">
        <td>${r.id}</td>
        <td>${esc(r.artist_name ? r.artist_name + " — " : "")}${esc(r.title)}</td>
        <td>${esc(fmt(r.preorder_opens_at))}</td>
        <td>${r.links.length ? esc(r.links.map((l) => l.shop_name).join(", ")) : "-"}</td>
        <td>${r.is_published ? "공개" : "초안"}</td>
        <td>
          <button data-act="edit" data-id="${r.id}">수정</button>
          ${r.is_published
            ? `<button data-act="unpublish" data-id="${r.id}">공개 취소</button>`
            : `<button class="pub" data-act="publish" data-id="${r.id}">공개</button>`}
          ${r.can_delete
            ? `<button data-act="delete" data-id="${r.id}">삭제</button>`
            : ""}
        </td>
      </tr>`).join("");

    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    $("#list tbody").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", async () => {
        const id = b.dataset.id;
        try {
          switch (b.dataset.act) {
            case "edit":
              startEdit(byId[id]);
              return;
            case "publish":
              await api(`/admin/releases/${id}/publish`, { method: "POST" });
              show(`#${id} 공개됨`, true);
              break;
            case "unpublish":
              await api(`/admin/releases/${id}/unpublish`, { method: "POST" });
              show(`#${id} 공개 취소됨 (구독자에게 나간 알림은 남습니다)`, true);
              break;
            case "delete":
              if (!confirm(`#${id} 을(를) 삭제할까요? 되돌릴 수 없습니다.`)) return;
              await api(`/admin/releases/${id}`, { method: "DELETE" });
              show(`#${id} 삭제됨`, true);
              if (editingId === Number(id)) resetForm();
              break;
          }
          load();
        } catch (err) {
          show(String(err.message), false);
        }
      }));
  } catch (err) {
    show(String(err.message), false);
  }
}
$("#reload").addEventListener("click", load);

// ── 최초 진입 ───────────────────────────────────────────────
// 저장된 키가 있어도 **그대로 믿지 않는다.** 서버에서 키를 바꿨을 수 있으므로
// 한 번 확인하고 들어간다 — 아니면 화면은 열리는데 모든 동작이 401 로 실패한다.
(async () => {
  // 마크업의 hidden 속성에만 기대지 않는다 — 순서가 바뀌어도 키 없이 본문이 열리면 안 된다.
  $("#app").hidden = true;
  $("#login").hidden = false;
  if (!adminKey) { $("#key").focus(); return; }
  try {
    if (await verifyKey(adminKey)) {
      enterApp();
      await load();
    } else {
      leaveApp("세션이 만료되었습니다. 다시 로그인하십시오.");
    }
  } catch {
    leaveApp("서버에 연결하지 못했습니다.");
  }
})();
</script>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_form() -> HTMLResponse:
    """운영자 등록 화면. 인증은 브라우저에서 입력한 키로 API 호출 시 이루어진다."""
    return HTMLResponse(_PAGE)
