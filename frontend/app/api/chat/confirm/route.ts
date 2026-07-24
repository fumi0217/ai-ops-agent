import { NextRequest, NextResponse } from "next/server";
import { CHAT_API_URL } from "@/lib/config";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const resp = await fetch(`${CHAT_API_URL}/chat/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await resp.json();
  if (!resp.ok) {
    return NextResponse.json({ error: data.detail ?? "予期しないエラーが発生しました。" }, { status: resp.status });
  }
  return NextResponse.json(data);
}
