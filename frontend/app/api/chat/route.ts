import { NextRequest, NextResponse } from "next/server";
import { CHAT_API_URL } from "@/lib/config";

// Proxies to chat_api over the internal docker network. The browser never
// talks to chat_api directly — only this server-side handler does, so no
// CORS setup is needed on the Python side.
//
// chat_api streams a successful turn as Server-Sent Events (see
// chat/api.py's _stream_events, ADR-0014), so on success this handler just
// passes the response body stream straight through unread. A non-2xx here
// means the request never got that far (e.g. FastAPI request validation
// rejecting a malformed body) — that's still a plain JSON error, not a
// stream, so it's read and re-shaped as before.
export async function POST(req: NextRequest) {
  const body = await req.json();

  const resp = await fetch(`${CHAT_API_URL}/chat`, {
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
