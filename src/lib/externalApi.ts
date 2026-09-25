/**
 * External paper source API client.
 * Connects to the backend /api/v1/external endpoints which proxy
 * arXiv, PubMed, and Semantic Scholar.
 */
import { apiRequest } from "./api";

export interface ExternalPaper {
  title: string;
  authors: string;
  abstract: string;
  source: "arxiv" | "pubmed" | "semantic_scholar" | "core";
  external_id: string;
  url: string;
  published: string | null;
  doi: string | null;
  pdf_url: string | null;
}

export interface ExternalSearchResponse {
  query: string;
  sources: string[];
  total: number;
  papers: ExternalPaper[];
}

export interface IngestResponse {
  message: string;
  document_id: string;
  title: string;
  new_version_created: boolean;
  deduplicated: boolean;
}

/** Search arXiv, PubMed and/or Semantic Scholar via the backend. */
export async function searchExternalSources(
  query: string,
  sources: string[] = ["arxiv", "pubmed", "semantic_scholar"],
  maxPerSource = 8
): Promise<ExternalSearchResponse> {
  const params = new URLSearchParams({
    query,
    sources: sources.join(","),
    max_per_source: String(maxPerSource),
  });
  return apiRequest<ExternalSearchResponse>(`/external/search?${params}`);
}

/** Ingest an external paper into the RAG knowledge base. */
export async function ingestExternalPaper(
  paper: ExternalPaper
): Promise<IngestResponse> {
  return apiRequest<IngestResponse>("/external/ingest", {
    method: "POST",
    body: paper,
  });
}

// ── Source metadata helpers ──────────────────────────────────────────────────

export const SOURCE_META: Record<
  string,
  { label: string; color: string; bgClass: string; textClass: string; icon: string }
> = {
  arxiv: {
    label: "arXiv",
    color: "#b31b1b",
    bgClass: "bg-red-100 dark:bg-red-950/40",
    textClass: "text-red-700 dark:text-red-400",
    icon: "📄",
  },
  pubmed: {
    label: "PubMed",
    color: "#0070d9",
    bgClass: "bg-blue-100 dark:bg-blue-950/40",
    textClass: "text-blue-700 dark:text-blue-400",
    icon: "🧬",
  },
  semantic_scholar: {
    label: "Semantic Scholar",
    color: "#1fa64a",
    bgClass: "bg-emerald-100 dark:bg-emerald-950/40",
    textClass: "text-emerald-700 dark:text-emerald-400",
    icon: "🔬",
  },
  core: {
    label: "CORE",
    color: "#7c3aed",
    bgClass: "bg-violet-100 dark:bg-violet-950/40",
    textClass: "text-violet-700 dark:text-violet-400",
    icon: "🌐",
  },
};

export function getSourceMeta(source: string) {
  return SOURCE_META[source] ?? {
    label: source,
    color: "#888",
    bgClass: "bg-muted",
    textClass: "text-muted-foreground",
    icon: "📑",
  };
}

/** Build a direct URL to view a paper on its host platform. */
export function buildPaperUrl(paper: ExternalPaper): string {
  if (paper.url) return paper.url;
  switch (paper.source) {
    case "arxiv":
      return `https://arxiv.org/abs/${paper.external_id}`;
    case "pubmed":
      return `https://pubmed.ncbi.nlm.nih.gov/${paper.external_id}/`;
    case "semantic_scholar":
      return `https://www.semanticscholar.org/paper/${paper.external_id}`;
    default:
      return "#";
  }
}

/** Build a PDF URL when possible. */
export function buildPdfUrl(paper: ExternalPaper): string | null {
  // Use the backend-provided direct PDF URL first (Semantic Scholar OA, CORE download)
  if (paper.pdf_url) return paper.pdf_url;
  // For arXiv, always construct from the ID
  if (paper.source === "arxiv") {
    return `https://arxiv.org/pdf/${paper.external_id}`;
  }
  return null;
}
