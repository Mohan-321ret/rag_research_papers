/**
 * Central API client.
 *
 * Exports:
 *   - apiRequest / ApiError / onUnauthorized  (used by AuthContext + LoginPage)
 *   - fetchDashboard, fetchDocuments, fetchChatHistory, fetchProfile  (analytics/data)
 *   - hybridSearch, semanticSearch  (RAG search)
 */
import { getToken } from "./tokenStorage";

// ── Base URL ─────────────────────────────────────────────────────────────────

const BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

// ── Unauthorised callback (used by AuthContext to log user out on 401) ────────

let _onUnauthorized: (() => void) | null = null;
export function onUnauthorized(cb: () => void) {
  _onUnauthorized = cb;
}

// ── ApiError class (used by LoginPage, AuthContext) ───────────────────────────

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ── Original apiRequest used by AuthContext + LoginPage ───────────────────────

interface ApiRequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;      // default true — pass false for login/register
  headers?: Record<string, string>;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const { method = "GET", body, auth = true, headers: extraHeaders = {} } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    _onUnauthorized?.();
    throw new ApiError("Unauthorised", 401);
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch { /* ignore */ }
    throw new ApiError(message, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Internal helper used by new data-fetch functions ─────────────────────────

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers ?? {}),
    },
  });
  if (res.status === 401) {
    _onUnauthorized?.();
    throw new ApiError("Unauthorised", 401);
  }
  if (!res.ok) {
    let detail = `API error ${res.status}`;
    try { const d = await res.json(); if (d?.detail) detail = String(d.detail); } catch { /* */ }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Analytics / Dashboard ─────────────────────────────────────────────────────

export interface DashboardStats {
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  total_answers: number;
  avg_confidence: number | null;
  avg_latency_ms: number | null;
  hallucination_rate: number | null;
  drift_events: number;
  conflict_count: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  [key: string]: unknown;
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  const data = await req<any>("/analytics/dashboard");
  const stats: DashboardStats = {
    total_documents: data?.corpus?.documents ?? 0,
    total_chunks: data?.corpus?.chunks ?? 0,
    total_queries: data?.usage?.queries ?? 0,
    total_answers: data?.usage?.answers ?? 0,
    avg_confidence: data?.quality?.avg_confidence ?? null,
    avg_latency_ms: data?.quality?.avg_latency_ms ?? null,
    hallucination_rate: null,
    drift_events: typeof data?.drift === "object" && data.drift ? Object.values(data.drift).reduce((a: number, b: any) => a + Number(b), 0) : 0,
    conflict_count: typeof data?.conflicts === "number" ? data.conflicts : 0,
  };
  return { stats, ...data };
}

// ── Documents ─────────────────────────────────────────────────────────────────

export interface DocumentRead {
  id: string;
  title: string;
  source_uri: string | null;
  source_type: string;
  status: "pending" | "processing" | "ready" | "error";
  metadata: Record<string, unknown>;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
  current_version: number | null;
  version_count: number;
}

export interface DocumentListResponse {
  items: DocumentRead[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchDocuments(
  opts: { limit?: number; offset?: number; search?: string } = {}
): Promise<DocumentListResponse> {
  const p = new URLSearchParams();
  if (opts.limit) p.set("limit", String(opts.limit));
  if (opts.offset) p.set("offset", String(opts.offset));
  if (opts.search) p.set("search", opts.search);
  return req(`/documents?${p}`);
}

// ── Search (RAG) ──────────────────────────────────────────────────────────────

export interface SearchHit {
  chunk_id: string;
  document_id: string;
  document_name: string;
  version: number;
  page: number | null;
  section: string | null;
  score: number;
  snippet: string;
  retrievers: string[];
}

export interface SearchResponse {
  query: string;
  route: string;
  total: number;
  results: SearchHit[];
  reasons: string[];
  retriever_hits: Record<string, number>;
  fallback_used: boolean;
}

export async function hybridSearch(query: string, topK = 8): Promise<SearchResponse> {
  return req("/search/hybrid", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

export async function semanticSearch(query: string, topK = 8): Promise<SearchResponse> {
  return req("/search/semantic", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

// ── Chat history ──────────────────────────────────────────────────────────────

export interface ChatHistoryItem {
  query_id: string;
  query_text: string;
  intent: string;
  created_at: string;
  answers: {
    id: string;
    answer_text: string;
    model: string;
    latency_ms: number;
    grounded: boolean | null;
    confidence: number | null;
    created_at: string;
    citations: { marker: number; chunk_id: string; snippet: string }[];
  }[];
}

export interface ChatHistoryResponse {
  items: ChatHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchChatHistory(
  limit = 20,
  offset = 0
): Promise<ChatHistoryResponse> {
  return req(`/chat/history?limit=${limit}&offset=${offset}`);
}

// ── Auth / Profile ────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export async function fetchProfile(): Promise<UserProfile> {
  return req("/auth/me");
}
