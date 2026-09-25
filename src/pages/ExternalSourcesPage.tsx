import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Globe,
  SlidersHorizontal,
  AlertCircle,
  Loader2,
  CheckCircle2,
  BookOpen,
  FileText,
  FlaskConical,
  Sparkles,
  X,
  Library,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ExternalPaperCard } from "@/components/features/ExternalPaperCard";
import { useExternalSearch } from "@/hooks/useExternalSearch";
import { ingestExternalPaper, type ExternalPaper } from "@/lib/externalApi";
import { cn } from "@/lib/utils";

const SOURCE_OPTIONS = [
  {
    id: "arxiv",
    label: "arXiv",
    description: "Computer Science, Physics, Math",
    icon: <FileText className="h-4 w-4" />,
    colorClass: "text-red-600 dark:text-red-400",
    bgClass: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800",
    checkedBg: "bg-red-100 dark:bg-red-900/40",
  },
  {
    id: "pubmed",
    label: "PubMed",
    description: "Biomedical & Life Sciences",
    icon: <FlaskConical className="h-4 w-4" />,
    colorClass: "text-blue-600 dark:text-blue-400",
    bgClass: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800",
    checkedBg: "bg-blue-100 dark:bg-blue-900/40",
  },
  {
    id: "semantic_scholar",
    label: "Semantic Scholar",
    description: "All disciplines (AI-powered)",
    icon: <BookOpen className="h-4 w-4" />,
    colorClass: "text-emerald-600 dark:text-emerald-400",
    bgClass:
      "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800",
    checkedBg: "bg-emerald-100 dark:bg-emerald-900/40",
  },
  {
    id: "core",
    label: "CORE",
    description: "Open-access hub (200M+ papers)",
    icon: <Library className="h-4 w-4" />,
    colorClass: "text-violet-600 dark:text-violet-400",
    bgClass: "bg-violet-50 dark:bg-violet-950/30 border-violet-200 dark:border-violet-800",
    checkedBg: "bg-violet-100 dark:bg-violet-900/40",
  },
];

const SUGGESTED_QUERIES = [
  "Retrieval-Augmented Generation",
  "Large Language Model alignment",
  "Transformer self-attention mechanism",
  "Neural network interpretability",
  "Vector database similarity search",
  "In-context learning LLM",
];

export default function ExternalSourcesPage() {
  const [query, setQuery] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "arxiv",
    "pubmed",
    "semantic_scholar",
  ]);
  const [maxPerSource, setMaxPerSource] = useState(8);
  const [ingestingIds, setIngestingIds] = useState<Set<string>>(new Set());
  const [ingestedIds, setIngestedIds] = useState<Set<string>>(new Set());
  const [ingestError, setIngestError] = useState<string | null>(null);

  const { papers, total, isLoading, error, hasSearched, search, clearResults } =
    useExternalSearch();

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || selectedSources.length === 0) return;
    search(query, selectedSources, maxPerSource);
  };

  const handleSuggestedQuery = (q: string) => {
    setQuery(q);
    search(q, selectedSources, maxPerSource);
  };

  const toggleSource = (id: string) => {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handleIngest = useCallback(
    async (paper: ExternalPaper) => {
      const key = `${paper.source}:${paper.external_id}`;
      setIngestError(null);
      setIngestingIds((prev) => new Set(prev).add(key));
      try {
        await ingestExternalPaper(paper);
        setIngestedIds((prev) => new Set(prev).add(key));
      } catch (err) {
        setIngestError(
          err instanceof Error ? err.message : "Failed to ingest paper."
        );
      } finally {
        setIngestingIds((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    },
    []
  );

  const sourceCounts = papers.reduce<Record<string, number>>((acc, p) => {
    acc[p.source] = (acc[p.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-1"
      >
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-purple-600 text-white shadow-md">
            <Globe className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              External Research Sources
            </h1>
            <p className="text-sm text-muted-foreground">
              Search arXiv, PubMed &amp; Semantic Scholar — then add papers to your RAG
              knowledge base
            </p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* ── Left panel: controls ────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.05 }}
          className="lg:col-span-1 space-y-4"
        >
          {/* Source selector */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <SlidersHorizontal className="h-4 w-4" />
              Sources
            </div>
            <div className="space-y-2">
              {SOURCE_OPTIONS.map((src) => {
                const checked = selectedSources.includes(src.id);
                return (
                  <button
                    key={src.id}
                    onClick={() => toggleSource(src.id)}
                    className={cn(
                      "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition-all",
                      checked ? src.checkedBg + " border-primary/30" : src.bgClass
                    )}
                  >
                    {/* Custom checkbox */}
                    <div
                      className={cn(
                        "h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors",
                        checked
                          ? "bg-primary border-primary"
                          : "border-muted-foreground/40 bg-transparent"
                      )}
                    >
                      {checked && (
                        <svg viewBox="0 0 12 10" className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={2}>
                          <polyline points="1,5 4,9 11,1" />
                        </svg>
                      )}
                    </div>
                    <span className={cn("shrink-0", src.colorClass)}>{src.icon}</span>
                    <div className="min-w-0">
                      <p className="font-medium text-xs leading-tight">{src.label}</p>
                      <p className="text-xs text-muted-foreground leading-tight">
                        {src.description}
                      </p>
                    </div>
                    {hasSearched && sourceCounts[src.id] !== undefined && (
                      <Badge variant="secondary" className="ml-auto text-xs shrink-0">
                        {sourceCounts[src.id]}
                      </Badge>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Results per source */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <p className="text-sm font-semibold">Results per source</p>
            <div className="flex gap-2 flex-wrap">
              {[5, 8, 10, 15].map((n) => (
                <button
                  key={n}
                  onClick={() => setMaxPerSource(n)}
                  className={cn(
                    "px-3 py-1 rounded-lg border text-sm transition-all",
                    maxPerSource === n
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-muted/40 hover:bg-muted"
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Suggested queries */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-primary" />
              Quick searches
            </div>
            <div className="space-y-1.5">
              {SUGGESTED_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSuggestedQuery(q)}
                  className="w-full text-left text-xs px-3 py-2 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </motion.div>

        {/* ── Right panel: search + results ───────────────────────────────── */}
        <div className="lg:col-span-3 space-y-4">
          {/* Search bar */}
          <motion.form
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            onSubmit={handleSearch}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="e.g., transformer attention mechanisms in NLP…"
                className="pl-10 h-11 text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isLoading}
              />
              {query && (
                <button
                  type="button"
                  onClick={() => { setQuery(""); clearResults(); }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <Button
              type="submit"
              size="lg"
              className="px-6 gap-2"
              disabled={isLoading || !query.trim() || selectedSources.length === 0}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              {isLoading ? "Searching…" : "Search"}
            </Button>
          </motion.form>

          {/* Ingest error */}
          <AnimatePresence>
            {ingestError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 flex items-center gap-2 text-sm text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                {ingestError}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Search error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 flex items-start gap-2 text-sm text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <span>{error}</span>
                  {error.includes("server") && (
                    <span className="block mt-1 text-xs opacity-80">
                      Make sure the backend is running at{" "}
                      <code className="font-mono">
                        {import.meta.env.VITE_API_URL ?? "http://localhost:8000"}
                      </code>
                    </span>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results header */}
          {hasSearched && !isLoading && !error && (
            <div className="flex items-center gap-3">
              <p className="text-sm text-muted-foreground">
                Found{" "}
                <span className="font-semibold text-foreground">{total}</span>{" "}
                papers for{" "}
                <span className="font-semibold text-primary">"{query}"</span>
              </p>
              <Separator orientation="vertical" className="h-4" />
              {SOURCE_OPTIONS.filter((s) => selectedSources.includes(s.id)).map((s) => (
                <span
                  key={s.id}
                  className={cn("text-xs font-medium", s.colorClass)}
                >
                  {s.label}: {sourceCounts[s.id] ?? 0}
                </span>
              ))}
              {ingestedIds.size > 0 && (
                <>
                  <Separator orientation="vertical" className="h-4" />
                  <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {ingestedIds.size} added to knowledge base
                  </span>
                </>
              )}
            </div>
          )}

          {/* Empty / loading / results */}
          {!hasSearched && !isLoading ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-24 text-center"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-purple-600/20 mb-4 border border-primary/20">
                <Globe className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">
                Search External Research Databases
              </h3>
              <p className="text-sm text-muted-foreground max-w-md mb-6">
                Query arXiv, PubMed, and Semantic Scholar simultaneously. Discover
                papers and add them directly to your RAG knowledge base for AI-powered
                retrieval.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SOURCE_OPTIONS.map((s) => (
                  <span
                    key={s.id}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm border font-medium",
                      s.bgClass,
                      s.colorClass
                    )}
                  >
                    {s.icon}
                    {s.label}
                  </span>
                ))}
              </div>
            </motion.div>
          ) : isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-xl border bg-card p-4 space-y-3 animate-pulse"
                >
                  <div className="h-4 w-24 rounded bg-muted" />
                  <div className="h-4 w-full rounded bg-muted" />
                  <div className="h-4 w-3/4 rounded bg-muted" />
                  <div className="h-3 w-1/2 rounded bg-muted" />
                  <div className="h-8 w-32 rounded bg-muted" />
                </div>
              ))}
            </div>
          ) : papers.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-20 text-center"
            >
              <Search className="h-10 w-10 text-muted-foreground/40 mb-4" />
              <h3 className="font-semibold mb-1">No papers found</h3>
              <p className="text-sm text-muted-foreground max-w-sm">
                Try broadening your query or enabling more sources.
              </p>
            </motion.div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {papers.map((paper, i) => {
                const key = `${paper.source}:${paper.external_id}`;
                const alreadyIngested = ingestedIds.has(key);
                return (
                  <div key={key} className="relative">
                    {alreadyIngested && (
                      <div className="absolute -top-1.5 -right-1.5 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white shadow-md">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                    )}
                    <ExternalPaperCard
                      paper={paper}
                      index={i}
                      onIngest={alreadyIngested ? undefined : handleIngest}
                      isIngesting={ingestingIds.has(key)}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
