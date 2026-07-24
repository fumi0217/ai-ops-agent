"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { isDisplayMessage } from "@/lib/isDisplayMessage";
import type { ChatResponse, Message, PendingAction } from "@/lib/types";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");

  async function postJson(url: string, body: unknown): Promise<ChatResponse> {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error ?? "予期しないエラーが発生しました。");
    }
    return data as ChatResponse;
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const nextMessages: Message[] = [...messages, { role: "user", parts: [{ text }] }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const data = await postJson("/api/chat", { messages: nextMessages });
      setMessages(data.messages);
      setPendingAction(data.pending_action);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(confirmed: boolean) {
    if (!pendingAction) return;
    const action = pendingAction;
    setPendingAction(null);
    setError(null);
    setLoading(true);
    try {
      const data = await postJson("/api/chat/confirm", {
        messages,
        pending_action: action,
        confirmed,
      });
      setMessages(data.messages);
      setPendingAction(data.pending_action);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-4 p-6">
      <header className="border-b pb-4">
        <h1 className="text-2xl font-bold">🤖 AI Ops Agent</h1>
        <p className="text-sm text-muted-foreground">
          チャットで運用作業を自動化 | Powered by Gemini 2.5 Flash + MCP
        </p>
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
        {loading && <p className="text-sm text-muted-foreground">考えています...</p>}
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
