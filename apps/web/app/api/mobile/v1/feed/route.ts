import { mobileRead } from "@/lib/mobile-read";
export async function GET(request: Request) { return mobileRead(request, "feed"); }
