// Server-only: used exclusively inside Route Handlers, never sent to the browser.
export const CHAT_API_URL = process.env.CHAT_API_URL ?? "http://localhost:8003";
