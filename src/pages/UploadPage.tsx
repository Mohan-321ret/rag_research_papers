import { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Search,
  Database,
  Zap,
  FileUp,
  Clock,
  Hash,
  ChevronDown,
  ChevronUp,
  X,
  FileBadge,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  uploadDocument,
  listDocuments,
  deleteDocument,
  processDocument,
  hybridSearch,
  semanticSearch,
  type DocumentRead,
  type SearchHit,
  type SearchResponse,
} from "@/lib/documentsApi";
import { cn } from "@/lib/utils";

// ── helpers ──────────────────────────────────────────────────────────────────

const ACCEPTED = ".pdf,.docx,.txt,.html,.htm,.xlsx";
const ACCEPTED_LABEL = "PDF, DOCX, TXT, HTML, XLSX";
const MAX_MB = 25;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function statusColor(status: string): string {
  switch (status) {
    case "ready":
      return "text-emerald-600 dark:text-emerald-400";
    case "processing":
      return "text-amber-600 dark:text-amber-400";
    case "error":
      return "text-red-600 dark:text-red-400";
    default:
      return "text-muted-foreground";
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "ready":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 text-xs font-medium">
          <CheckCircle2 className="h-3 w-3" /> Ready for RAG
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 px-2 py-0.5 text-xs font-medium">
          <Loader2 className="h-3 w-3 animate-spin" /> Processing
        </span>
      );
    case "error":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-400 px-2 py-0.5 text-xs font-medium">
          <AlertCircle className="h-3 w-3" /> Error
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted text-muted-foreground px-2 py-0.5 text-xs font-medium">
          <Clock className="h-3 w-3" /> Pending
        </span>
      );
  }
}

// ── component ─────────────────────────────────────────────────────────────────

interface UploadingFile {
  file: File;
  title: string;
  author: string;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
  result?: DocumentRead;
}

export default function UploadPage() {
  // Upload state
  const [dragOver, setDragOver] = useState(false);
  const [queue, setQueue] = useState<UploadingFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Documents list state
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);
  const [docSearch, setDocSearch] = useState("");
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // RAG search state
  const [ragQuery, setRagQuery] = useState("");
  const [ragResults, setRagResults] = useState<SearchResponse | null>(null);
  const [ragLoading, setRagLoading] = useState(false);
  const [ragError, setRagError] = useState<string | null>(null);
  const [ragMode, setRagMode] = useState<"hybrid" | "semantic">("hybrid");
  const [expandedHits, setExpandedHits] = useState<Set<string>>(new Set());

  // ── load documents ──────────────────────────────────────────────────────────

  const loadDocuments = useCallback(async () => {
    setDocsLoading(true);
    setDocsError(null);
    try {
      const res = await listDocuments({ limit: 100, search: docSearch || undefined });
      setDocuments(res.items);
    } catch (e) {
      setDocsError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setDocsLoading(false);
    }
  }, [docSearch]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // ── drag & drop ─────────────────────────────────────────────────────────────

  const addFiles = useCallback((files: FileList | null) => {
    if (!files) return;
    const newItems: UploadingFile[] = [];
    for (const file of Array.from(files)) {
      if (file.size > MAX_MB * 1024 * 1024) continue; // skip oversized
      newItems.push({ file, title: file.name.replace(/\.[^.]+$/, ""), author: "", status: "queued" });
    }
    setQueue((prev) => [...prev, ...newItems]);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  // ── upload queue ────────────────────────────────────────────────────────────

  const startUpload = useCallback(async () => {
    const toUpload = queue.filter((q) => q.status === "queued");
    if (!toUpload.length) return;
    setIsUploading(true);

    for (const item of toUpload) {
      setQueue((prev) =>
        prev.map((q) => (q.file === item.file ? { ...q, status: "uploading" } : q))
      );
      try {
        const result = await uploadDocument(item.file, {
          title: item.title || undefined,
          author: item.author || undefined,
        });
        setQueue((prev) =>
          prev.map((q) =>
            q.file === item.file ? { ...q, status: "done", result } : q
          )
        );
      } catch (e) {
        setQueue((prev) =>
          prev.map((q) =>
            q.file === item.file
              ? { ...q, status: "error", error: e instanceof Error ? e.message : "Upload failed" }
              : q
          )
        );
      }
    }

    setIsUploading(false);
    await loadDocuments();
  }, [queue, loadDocuments]);

  const removeFromQueue = (file: File) =>
    setQueue((prev) => prev.filter((q) => q.file !== file));

  const updateQueueItem = (file: File, patch: Partial<UploadingFile>) =>
    setQueue((prev) => prev.map((q) => (q.file === file ? { ...q, ...patch } : q)));

  // ── process / delete ────────────────────────────────────────────────────────

  const handleProcess = async (docId: string) => {
    setProcessingIds((prev) => new Set(prev).add(docId));
    try {
      await processDocument(docId);
      await loadDocuments();
    } catch {
      // silently update — status will show on reload
    } finally {
      setProcessingIds((prev) => {
        const s = new Set(prev);
        s.delete(docId);
        return s;
      });
    }
  };

  const handleDelete = async (docId: string) => {
    setDeletingIds((prev) => new Set(prev).add(docId));
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      /* ignore */
    } finally {
      setDeletingIds((prev) => {
        const s = new Set(prev);
        s.delete(docId);
        return s;
      });
    }
  };

  // ── RAG search ──────────────────────────────────────────────────────────────

  const handleRagSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;
    setRagLoading(true);
    setRagError(null);
    setRagResults(null);
    try {
      const fn = ragMode === "hybrid" ? hybridSearch : semanticSearch;
      const res = await fn(ragQuery, 8);
      setRagResults(res);
    } catch (e) {
      setRagError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setRagLoading(false);
    }
  };

  const toggleHit = (id: string) =>
    setExpandedHits((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });

  const readyCount = documents.filter((d) => d.status === "ready").length;
  const pendingCount = documents.filter((d) => d.status === "pending" || d.status === "processing").length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-1"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-indigo-600 text-white shadow-md">
            <FileUp className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Upload Papers</h1>
            <p className="text-sm text-muted-foreground">
              Upload PDFs, DOCX, or text files — they are chunked, embedded, and indexed into the RAG knowledge base automatically
            </p>
          </div>
        </div>

        {/* Stats bar */}
        <div className="flex flex-wrap gap-4 pt-2">
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Database className="h-4 w-4 text-primary" />
            <span className="font-semibold text-foreground">{documents.length}</span> documents
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <span className="font-semibold text-foreground">{readyCount}</span> ready for RAG
          </div>
          {pendingCount > 0 && (
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />
              <span className="font-semibold text-foreground">{pendingCount}</span> processing
            </div>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-8">
        {/* ── LEFT: Upload + Document list ───────────────────────────────── */}
        <div className="xl:col-span-3 space-y-6">

          {/* Drop zone */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 }}
          >
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-200 py-14 px-6 text-center",
                dragOver
                  ? "border-primary bg-primary/5 scale-[1.01]"
                  : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30"
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ACCEPTED}
                className="sr-only"
                onChange={(e) => addFiles(e.target.files)}
              />
              <motion.div
                animate={{ scale: dragOver ? 1.15 : 1 }}
                transition={{ type: "spring", stiffness: 300 }}
                className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-indigo-600/20 border border-primary/20 mb-4"
              >
                <Upload className="h-8 w-8 text-primary" />
              </motion.div>
              <p className="text-base font-semibold mb-1">
                {dragOver ? "Drop files here" : "Drag & drop files, or click to browse"}
              </p>
              <p className="text-sm text-muted-foreground">
                {ACCEPTED_LABEL} · Max {MAX_MB} MB per file
              </p>
              <p className="text-xs text-muted-foreground mt-2 opacity-70">
                Files are automatically chunked, embedded, and added to the RAG index
              </p>
            </div>
          </motion.div>

          {/* Upload queue */}
          <AnimatePresence>
            {queue.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <FileBadge className="h-4 w-4 text-primary" />
                    Upload Queue ({queue.length})
                  </h3>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => setQueue([])}
                    >
                      Clear All
                    </Button>
                    <Button
                      size="sm"
                      className="h-7 text-xs gap-1.5"
                      onClick={startUpload}
                      disabled={isUploading || queue.every((q) => q.status !== "queued")}
                    >
                      {isUploading ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Upload className="h-3 w-3" />
                      )}
                      {isUploading ? "Uploading…" : "Upload All"}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  {queue.map((item, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                      className="rounded-xl border bg-card p-3 space-y-2"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div className="flex-1 min-w-0 space-y-1.5">
                          <Input
                            value={item.title}
                            onChange={(e) => updateQueueItem(item.file, { title: e.target.value })}
                            placeholder="Paper title"
                            className="h-7 text-xs"
                            disabled={item.status !== "queued"}
                          />
                          <Input
                            value={item.author}
                            onChange={(e) => updateQueueItem(item.file, { author: e.target.value })}
                            placeholder="Author(s) — optional"
                            className="h-7 text-xs"
                            disabled={item.status !== "queued"}
                          />
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="truncate">{item.file.name}</span>
                            <span className="shrink-0">·</span>
                            <span className="shrink-0">{formatBytes(item.file.size)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {item.status === "uploading" && (
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                          )}
                          {item.status === "done" && (
                            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                          )}
                          {item.status === "error" && (
                            <AlertCircle className="h-4 w-4 text-red-500" title={item.error} />
                          )}
                          {(item.status === "queued" || item.status === "error") && (
                            <button
                              onClick={() => removeFromQueue(item.file)}
                              className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      {item.status === "error" && item.error && (
                        <p className="text-xs text-red-500 pl-12">{item.error}</p>
                      )}
                      {item.status === "done" && item.result && (
                        <p className="text-xs text-emerald-600 dark:text-emerald-400 pl-12">
                          ✓ Uploaded — {item.result.deduplicated ? "deduplicated (content already exists)" : item.result.new_version_created ? "new version created" : "added to knowledge base"}
                        </p>
                      )}
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Documents list */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold flex-1 flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" />
                Knowledge Base Documents
              </h3>
              <div className="relative w-48">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Search…"
                  value={docSearch}
                  onChange={(e) => setDocSearch(e.target.value)}
                  className="pl-8 h-8 text-xs"
                />
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0"
                onClick={loadDocuments}
                disabled={docsLoading}
                title="Refresh"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", docsLoading && "animate-spin")} />
              </Button>
            </div>

            {docsError && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {docsError}
              </div>
            )}

            {docsLoading && documents.length === 0 ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-xl border bg-card p-4 animate-pulse">
                    <div className="flex gap-3">
                      <div className="h-10 w-10 rounded-lg bg-muted" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-3/4 rounded bg-muted" />
                        <div className="h-3 w-1/2 rounded bg-muted" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center rounded-xl border border-dashed">
                <Database className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="font-medium text-muted-foreground">No documents yet</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Upload files above to populate the RAG knowledge base
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border bg-card p-3 flex items-start gap-3 group hover:border-primary/30 transition-all"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <p className="font-medium text-sm truncate">{doc.title}</p>
                      <div className="flex flex-wrap items-center gap-2">
                        {statusBadge(doc.status)}
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Hash className="h-3 w-3" />v{doc.current_version ?? 1}
                        </span>
                        <span className="text-xs text-muted-foreground capitalize">
                          {doc.source_type}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      {(doc.status === "pending" || doc.status === "error") && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs gap-1"
                          disabled={processingIds.has(doc.id)}
                          onClick={() => handleProcess(doc.id)}
                          title="Run RAG pipeline (chunk + embed)"
                        >
                          {processingIds.has(doc.id) ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Zap className="h-3 w-3" />
                          )}
                          Process
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-red-500 transition-colors"
                        disabled={deletingIds.has(doc.id)}
                        onClick={() => handleDelete(doc.id)}
                        title="Delete document"
                      >
                        {deletingIds.has(doc.id) ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: RAG Search ──────────────────────────────────────────── */}
        <div className="xl:col-span-2 space-y-4">
          <Card className="sticky top-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white">
                  <Zap className="h-3.5 w-3.5" />
                </div>
                Test RAG Retrieval
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Query the knowledge base to verify uploaded papers are indexed and retrievable
              </p>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Mode selector */}
              <div className="flex rounded-lg border p-0.5 gap-0.5 bg-muted/40">
                {(["hybrid", "semantic"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setRagMode(mode)}
                    className={cn(
                      "flex-1 rounded-md py-1.5 text-xs font-medium transition-all",
                      ragMode === mode
                        ? "bg-background shadow-sm text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {mode === "hybrid" ? "🔀 Hybrid (BM25 + Vector + Graph)" : "🔢 Semantic (Vector only)"}
                  </button>
                ))}
              </div>

              {/* Search form */}
              <form onSubmit={handleRagSearch} className="space-y-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={ragQuery}
                    onChange={(e) => setRagQuery(e.target.value)}
                    placeholder="e.g. How does attention work in transformers?"
                    className="pl-10 text-sm"
                    disabled={ragLoading}
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full gap-2"
                  disabled={ragLoading || !ragQuery.trim()}
                >
                  {ragLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  {ragLoading ? "Searching…" : "Search Knowledge Base"}
                </Button>
              </form>

              {/* Error */}
              {ragError && (
                <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 flex items-center gap-2 text-xs text-destructive">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {ragError}
                </div>
              )}

              {/* Results */}
              {ragResults && (
                <div className="space-y-3">
                  <Separator />
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      <span className="font-semibold text-foreground">{ragResults.total}</span> chunks retrieved
                      via <span className="font-medium text-foreground">{ragResults.route}</span>
                    </span>
                    {ragResults.fallback_used && (
                      <Badge variant="outline" className="text-xs">fallback</Badge>
                    )}
                  </div>

                  {ragResults.results.length === 0 ? (
                    <div className="text-center py-6 text-sm text-muted-foreground">
                      No relevant chunks found. Try uploading more papers or rephrasing your query.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[55vh] overflow-y-auto pr-1">
                      {ragResults.results.map((hit, i) => (
                        <div key={hit.chunk_id} className="rounded-lg border bg-muted/30 p-3 space-y-1.5">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-semibold text-foreground truncate">
                                {hit.document_name}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-xs text-muted-foreground">
                                  score: <span className="font-medium text-primary">{(hit.score * 100).toFixed(0)}%</span>
                                </span>
                                {hit.page && (
                                  <span className="text-xs text-muted-foreground">p.{hit.page}</span>
                                )}
                                <span className="text-xs text-muted-foreground capitalize">
                                  [{hit.retrievers.join(", ")}]
                                </span>
                              </div>
                            </div>
                            <button
                              onClick={() => toggleHit(hit.chunk_id)}
                              className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                            >
                              {expandedHits.has(hit.chunk_id) ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>
                          </div>
                          <AnimatePresence>
                            {expandedHits.has(hit.chunk_id) && (
                              <motion.p
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="text-xs text-muted-foreground leading-relaxed overflow-hidden"
                              >
                                {hit.snippet}
                              </motion.p>
                            )}
                          </AnimatePresence>
                          {!expandedHits.has(hit.chunk_id) && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {hit.snippet}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Retriever breakdown */}
                  {Object.keys(ragResults.retriever_hits).length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {Object.entries(ragResults.retriever_hits).map(([k, v]) => (
                        <span key={k} className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {k}: <span className="font-medium text-foreground">{v}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
