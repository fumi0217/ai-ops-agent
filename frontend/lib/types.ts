// Gemini content format — see chat/engine.py's module docstring. Held
// client-side in full and round-tripped through chat_api on every request.

export type TextPart = { text: string };
export type FunctionCallPart = { function_call: { name: string; args: Record<string, unknown> } };
export type FunctionResponsePart = {
  function_response: { name: string; response: Record<string, unknown> };
};
export type MessagePart = TextPart | FunctionCallPart | FunctionResponsePart;

export type Message = {
  role: "user" | "model";
  parts: MessagePart[];
};

export type PendingAction = {
  tool_name: string;
  tool_input: Record<string, unknown>;
  label: string;
  warning: string;
  description: string;
  // Opaque to the client — round-trip only, never render.
  sibling_responses: unknown[];
};

export type ChatResponse = {
  messages: Message[];
  reply: string;
  pending_action: PendingAction | null;
};

export type ChatErrorResponse = {
  error: string;
};

// POST /chat and /chat/confirm stream these as Server-Sent Events instead of
// a single JSON body (see chat/api.py's _stream_events, ADR-0014) so the UI
// can show MCP tool calls in real time while the agentic loop is running.
export type ToolCallEvent = {
  type: "tool_call";
  phase: "start" | "end";
  tool_name: string;
  tool_input: Record<string, unknown>;
  label: string;
  is_error?: boolean;
};

export type FinalEvent = ChatResponse & { type: "final" };

export type ErrorEvent = { type: "error"; detail: string };

export type StreamEvent = ToolCallEvent | FinalEvent | ErrorEvent;

// GET /audit-log — one entry per confirmed-and-executed mutating tool call
// (restart_service / scale_service). Read-only tool calls and cancelled
// confirmations are never recorded (see chat/audit.py, ADR-0014).
export type AuditLogEntry = {
  timestamp: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  label: string;
  is_error: boolean;
  result: string;
};
