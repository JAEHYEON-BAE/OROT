import { forward } from "@/lib/proxy";

export async function GET(request: Request) {
  const value = new URL(request.url).searchParams.get("include_release_dates");
  const query = value === null ? "" : `?include_release_dates=${encodeURIComponent(value)}`;
  return forward(`/v1/releases.ics${query}`);
}
