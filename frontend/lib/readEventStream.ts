import type { StreamEvent } from "./types";

/**
 * Parses a `text/event-stream` Response body (see chat/api.py's
 * _stream_events) into StreamEvent objects, one per `data: {...}` frame.
 * Frames are separated by a blank line ("\n\n"), per the SSE spec; we only
 * ever emit single-line `data:` frames server-side, so no multi-line
 * `data:`-field folding is needed here.
 */
export async function* readEventStream(resp: Response): AsyncGenerator<StreamEvent> {
  if (!resp.body) return;
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      yield JSON.parse(line.slice("data:".length).trim()) as StreamEvent;
    }
  }

  // `decoder.decode(..., { stream: true })` above can hold back a trailing
  // multi-byte sequence split across a chunk boundary — flush it here so it
  // isn't silently dropped (the payload is Japanese text throughout, so this
  // is a real, not just theoretical, split point). Server frames always end
  // in "\n\n" (see chat/api.py's _format_sse), so `buffer` is normally empty
  // by now; this also catches the rare case of a connection that closed
  // before that trailing "\n\n" arrived.
  buffer += decoder.decode();
  const line = buffer.trim();
  if (line.startsWith("data:")) {
    yield JSON.parse(line.slice("data:".length).trim()) as StreamEvent;
  }
}
