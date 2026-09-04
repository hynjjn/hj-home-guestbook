import { allTokens } from "./tokens";
import type { Entry, Feed } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      body && typeof body.detail === "string" ? body.detail : "요청이 실패했어요";
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export function fetchEntries(params: { limit?: number; before?: number } = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  if (params.before) query.set("before", String(params.before));

  const tokens = allTokens();
  return fetch(`${BASE}/entries?${query}`, {
    headers: tokens.length ? { "X-Edit-Tokens": tokens.join(",") } : {},
  }).then((r) => unwrap<Feed>(r));
}

export function createEntry(input: {
  name: string;
  content: string;
  pin: string;
  photo?: File | null;
}) {
  const form = new FormData();
  form.set("name", input.name);
  form.set("content", input.content);
  form.set("pin", input.pin);
  if (input.photo) form.set("photo", input.photo);

  return fetch(`${BASE}/entries`, { method: "POST", body: form }).then((r) =>
    unwrap<{ id: number; edit_token: string }>(r),
  );
}

/** PIN은 URL에 실으면 Cloudflare 로그, 접근 로그, 브라우저 히스토리에 남는다. 그래서 POST body. */
export function verifyPin(id: number, pin: string) {
  return fetch(`${BASE}/entries/${id}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  }).then((r) => unwrap<{ edit_token: string; content: string }>(r));
}

export function patchEntry(id: number, token: string, content: string) {
  return fetch(`${BASE}/entries/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-Edit-Token": token },
    body: JSON.stringify({ content }),
  }).then((r) => unwrap<Entry>(r));
}

export function deleteEntry(id: number, token: string) {
  return fetch(`${BASE}/entries/${id}`, {
    method: "DELETE",
    headers: { "X-Edit-Token": token },
  }).then((r) => unwrap<void>(r));
}
