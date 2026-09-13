import { mobileRead } from "@/lib/mobile-read";
export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  return mobileRead(request, "detail", (await context.params).id);
}
