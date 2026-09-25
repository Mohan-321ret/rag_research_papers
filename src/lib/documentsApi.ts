/**
 * Document upload & management API client.
 * Wraps /api/v1/documents and /api/v1/search endpoints.
 */
import { getToken } from "./tokenStorage";

const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

// ── Types ────────────────────────────────────────────────────────────────────

export type DocumentStatus = "pending" | "processing" | "ready" | "error";

export interface DocumentRead {
  id: string;
  title: string;
  source_uri: string | null;
  source_type: string;
  status: DocumentStatus;
  metadata: Record<string, unknown>;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
  current_version: number | null;
  version_count: number;
}

export interface UploadResponse extends DocumentRead {
  new_version_created: boolean;
  deduplicated: boolean;
}

export interface DocumentListResponse {
  items: DocumentRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProcessingResult {
  document_id: string;
  version: number;
  chunks_created: number;
  embeddings_created: number;
  processing_time_ms: number;
  status: string;
}

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

// ── Helpers ─────────────────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") msg = data.detail;
    } catch {
      // ignore non-JSON bodies
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── API calls ────────────────────────────────────────────────────────────────

/**
 * Upload a file (PDF, DOCX, TXT, HTML, XLSX).
 * Uses multipart/form-data — do NOT set Content-Type manually.
 */
export async function uploadDocument(
  file: File,
  opts: {
    title?: string;
    author?: string;
    department?: string;
    access_level?: string;
    priority?: number;
  } = {}
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (opts.title) form.append("title", opts.title);
  if (opts.author) form.append("author", opts.author);
  if (opts.department) form.append("department", opts.department);
  if (opts.access_level) form.append("access_level", opts.access_level);
  if (opts.priority !== undefined) form.append("priority", String(opts.priority));

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: { ...authHeaders() }, // no Content-Type — browser sets multipart boundary
    body: form,
  });
  return handleJson<UploadResponse>(res);
}

/** List all documents in the knowledge base. */
export async function listDocuments(opts: {
  limit?: number;
  offset?: number;
  search?: string;
} = {}): Promise<DocumentListResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  if (opts.search) params.set("search", opts.search);

  const res = await fetch(`${API_BASE}/documents?${params}`, {
    headers: { ...authHeaders() },
  });
  return handleJson<DocumentListResponse>(res);
}

/** Delete a document from the knowledge base. */
export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok && res.status !== 204) await handleJson<void>(res);
}

/** Trigger the RAG processing pipeline (chunking + embedding) on a document. */
export async function processDocument(documentId: string): Promise<ProcessingResult> {
  const res = await fetch(`${API_BASE}/documents/${documentId}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
  });
  return handleJson<ProcessingResult>(res);
}

/** Run hybrid RAG search (BM25 + vector + graph). */
export async function hybridSearch(query: string, topK = 8): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search/hybrid`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ query, top_k: topK }),
  });
  return handleJson<SearchResponse>(res);
}

/** Run pure vector / semantic search. */
export async function semanticSearch(query: string, topK = 8): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ query, top_k: topK }),
  });
  return handleJson<SearchResponse>(res);
}
