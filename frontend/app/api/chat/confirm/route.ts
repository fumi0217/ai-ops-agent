import { NextRequest, NextResponse } from "next/server";
import { CHAT_API_URL } from "@/lib/config";

// See app/api/chat/route.ts's comment — same streaming pass-through pattern.
export async function POST(req: NextRequest) {
  const body = await req.json();

  const resp = await fetch(`${CHAT_API_URL}/chat/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok || !resp.body) {
    const data = await resp.json().catch(() => ({}));
    return NextResponse.json(
      { error: data.detail ?? "予期しないエラーが発生しました。" },
      { status: resp.status || 502 }
    );
  }

  return new NextResponse(resp.body, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}
