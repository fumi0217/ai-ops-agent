"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { isDisplayMessage } from "@/lib/isDisplayMessage";
import { readEventStream } from "@/lib/readEventStream";
import type { Message, PendingAction, ToolCallEvent } from "@/lib/types";

function applyToolCallEvent(prev: ToolCallEvent[], event: ToolCallEvent): ToolCallEvent[] {
  if (event.phase === "start") return [...prev, event];
  // "end": tool calls execute one at a time (see chat/engine.py's agentic
  // loop), so the most recent entry is always the one this completes.
  return prev.map((t, i) => (i === prev.length - 1 ? event : t));
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [activeTools, setActiveTools] = useState<ToolCallEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");

  // Runs one streamed turn against `url`, updating messages/pendingAction
  // from the terminal `final` event and activeTools from each `tool_call`
  // event as it arrives — this is what shows the agent's MCP tool calls in
  // real time while it's still "thinking" (see ADR-0014).
  async function streamTurn(url: string, body: unknown) {
    setActiveTools([]);
    setError(null);
    setLoading(true);
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok || !resp.body) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error ?? "予期しないエラーが発生しました。");
      }
      for await (const event of readEventStream(resp)) {
        if (event.type === "tool_call") {
          setActiveTools((prev) => applyToolCallEvent(prev, event));
        } else if (event.type === "final") {
          setMessages(event.messages);
          setPendingAction(event.pending_action);
        } else if (event.type === "error") {
          throw new Error(event.detail);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const nextMessages: Message[] = [...messages, { role: "user", parts: [{ text }] }];
    setMessages(nextMessages);
    setInput("");
    await streamTurn("/api/chat", { messages: nextMessages });
  }

  async function handleConfirm(confirmed: boolean) {
    if (!pendingAction) return;
    const action = pendingAction;
    setPendingAction(null);
    await streamTurn("/api/chat/confirm", { messages, pending_action: action, confirmed });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-4 p-6">
      <header className="flex items-start justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold">🤖 AI Ops Agent</h1>
          <p className="text-sm text-muted-foreground">
            チャットで運用作業を自動化 | Powered by Gemini 2.5 Flash + MCP
          </p>
        </div>
        <Link href="/audit" className="whitespace-nowrap text-sm text-muted-foreground underline">
          監査ログ →
        </Link>
      </header>

      <div className="flex flex-1 flex-col gap-3">
        {messages.map((msg, i) => {
          const { shouldDisplay, text } = isDisplayMessage(msg);
          if (!shouldDisplay || !text) return null;
          const isUser = msg.role === "user";
          return (
            <div key={i} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-4 py-2 text-sm ${
                  isUser ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                {text}
              </div>
            </div>
          );
        })}
        {loading && (
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>考えています...</p>
            {activeTools.map((t, i) => (
              <p key={i}>
                {t.phase === "start" ? "🔧" : t.is_error ? "❌" : "✅"} {t.label}
                {t.phase === "start" ? " 実行中..." : t.is_error ? " 失敗" : " 完了"}
              </p>
            ))}
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>エラー</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {pendingAction ? (
        <Card className="border-yellow-500">
          <CardHeader>
            <CardTitle>⚠️ 確認: {pendingAction.label}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="whitespace-pre-wrap text-sm">{pendingAction.description}</p>
            {pendingAction.warning && (
              <Alert>
                <AlertDescription>{pendingAction.warning}</AlertDescription>
              </Alert>
            )}
            <div className="flex gap-2">
              <Button className="flex-1" disabled={loading} onClick={() => handleConfirm(true)}>
                ✅ 実行する
              </Button>
              <Button
                className="flex-1"
                variant="outline"
                disabled={loading}
                onClick={() => handleConfirm(false)}
              >
                ❌ キャンセル
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="flex gap-2 border-t pt-4">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="例: 全サービスの状況を確認して / payment-serviceのCPUが高い、対処して"
            disabled={loading}
            rows={2}
          />
          <Button onClick={handleSend} disabled={loading || !input.trim()}>
            送信
          </Button>
        </div>
      )}
    </main>
  );
}
