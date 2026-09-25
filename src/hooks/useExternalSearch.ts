import { useState, useCallback, useRef } from "react";
import {
  searchExternalSources,
  type ExternalPaper,
  type ExternalSearchResponse,
} from "@/lib/externalApi";

interface UseExternalSearchState {
  papers: ExternalPaper[];
  query: string;
  sources: string[];
  total: number;
  isLoading: boolean;
  error: string | null;
  hasSearched: boolean;
}

interface UseExternalSearchReturn extends UseExternalSearchState {
  search: (query: string, sources?: string[], maxPerSource?: number) => Promise<void>;
  clearResults: () => void;
}

const INITIAL_STATE: UseExternalSearchState = {
  papers: [],
  query: "",
  sources: [],
  total: 0,
  isLoading: false,
  error: null,
  hasSearched: false,
};

/**
 * Hook that wraps the backend /external/search endpoint.
 * Cancels in-flight requests when a new search is triggered.
 */
export function useExternalSearch(): UseExternalSearchReturn {
  const [state, setState] = useState<UseExternalSearchState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(
    async (
      query: string,
      sources: string[] = ["arxiv", "pubmed", "semantic_scholar"],
      maxPerSource = 8
    ) => {
      if (!query.trim()) return;

      // Cancel any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setState((prev) => ({
        ...prev,
        isLoading: true,
        error: null,
        hasSearched: true,
        query,
        sources,
      }));

      try {
        const result: ExternalSearchResponse = await searchExternalSources(
          query,
          sources,
          maxPerSource
        );
        setState((prev) => ({
          ...prev,
          papers: result.papers,
          total: result.total,
          isLoading: false,
        }));
      } catch (err: unknown) {
        // Ignore abort errors (user started a new search)
        if (err instanceof Error && err.name === "AbortError") return;
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error:
            err instanceof Error
              ? err.message
              : "Failed to fetch papers. Check your connection.",
        }));
      }
    },
    []
  );

  const clearResults = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, search, clearResults };
}
