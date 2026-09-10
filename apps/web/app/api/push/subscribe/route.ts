import type { NextRequest } from "next/server";

import { forward } from "@/lib/proxy";

const JSON_HEADERS = { "Content-Type": "application/json" };

export async function POST(request: NextRequest) {
  return forward("/v1/push/subscribe", {
    method: "POST",
    headers: JSON_HEADERS,
    body: await request.text(),
  });
}

export async function DELETE(request: NextRequest) {
  // DELETE 에 본문을 싣는다 — 해지에 필요한 것은 endpoint 뿐이고,
  // 엔드포인트 URL 은 쿼리스트링에 넣기엔 너무 길다.
  return forward("/v1/push/subscribe", {
    method: "DELETE",
    headers: JSON_HEADERS,
    body: await request.text(),
  });
}
