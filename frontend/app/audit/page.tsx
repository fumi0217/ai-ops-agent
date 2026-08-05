import Link from "next/link";
import { CHAT_API_URL } from "@/lib/config";
import type { AuditLogEntry } from "@/lib/types";

// Server Component, not a Route Handler + client fetch: unlike app/page.tsx
// (a client component that needs a Route Handler proxy because it can't see
// server-only env vars), this page has no client-side interactivity, so it
// can just fetch chat_api directly at render time. force-dynamic avoids
// Next.js caching a stale snapshot of an in-memory log that changes on the
// server between requests (see chat/audit.py, ADR-0014).
export const dynamic = "force-dynamic";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });
}

function formatDetail(toolInput: Record<string, unknown>): string {
  return Object.entries(toolInput)
    .filter(([key]) => key !== "service_name")
    .map(([key, value]) => `${key}: ${value}`)
    .join(" / ");
}

async function getAuditLog(): Promise<AuditLogEntry[]> {
  const resp = await fetch(`${CHAT_API_URL}/audit-log`, { cache: "no-store" });
  if (!resp.ok) return [];
  return resp.json();
}

export default async function AuditLogPage() {
  const entries = await getAuditLog();

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-4 p-6">
      <header className="flex items-start justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold">📋 監査ログ</h1>
          <p className="text-sm text-muted-foreground">
            確認・実行された破壊的操作(再起動・スケール変更)の記録。インメモリ保持のため
            chat_api再起動でリセットされます。
          </p>
        </div>
        <Link href="/" className="whitespace-nowrap text-sm text-muted-foreground underline">
          ← チャットに戻る
        </Link>
      </header>

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">記録はまだありません。</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="p-3 font-medium">日時</th>
                <th className="p-3 font-medium">操作</th>
                <th className="p-3 font-medium">対象サービス</th>
                <th className="p-3 font-medium">詳細</th>
                <th className="p-3 font-medium">結果</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr key={i} className="border-t">
                  <td className="whitespace-nowrap p-3 text-muted-foreground">
                    {formatTimestamp(entry.timestamp)}
                  </td>
                  <td className="p-3">{entry.label}</td>
                  <td className="p-3">{String(entry.tool_input.service_name ?? "—")}</td>
                  <td className="p-3 text-muted-foreground">{formatDetail(entry.tool_input)}</td>
                  <td className="p-3">
                    {entry.is_error ? (
                      <span className="text-destructive">❌ 失敗: {entry.result}</span>
                    ) : (
                      <span>✅ 成功</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
