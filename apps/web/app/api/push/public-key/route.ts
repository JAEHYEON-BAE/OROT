import { forward } from "@/lib/proxy";

/** VAPID 공개키. 서비스워커도 구독 갱신 때 이 경로를 부른다. */
export async function GET() {
  return forward("/v1/push/public-key");
}
