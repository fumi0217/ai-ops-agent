import type { Message, TextPart } from "./types";

function isTextPart(part: Message["parts"][number]): part is TextPart {
  return "text" in part;
}

/**
 * Port of chat/engine.py's is_display_message: only parts with a "text" key
 * are shown in the UI; function_call / function_response parts are
 * history-only. A message with no text part at all is hidden entirely.
 */
export function isDisplayMessage(message: Message): { shouldDisplay: boolean; text: string } {
  const textParts = message.parts.filter(isTextPart);
  if (textParts.length === 0) {
    return { shouldDisplay: false, text: "" };
  }
  return { shouldDisplay: true, text: textParts.map((p) => p.text).join(" ") };
}
