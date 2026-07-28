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
