import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Search,
  SlidersHorizontal,
  Globe,
  ArrowRight,
  FileText,
  Loader2,
  AlertCircle,
  BookOpen,
  ExternalLink,
  Hash,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { hybridSearch, semanticSearch, type SearchHit } from "@/lib/api";

type SearchMode = "hybrid" | "semantic";

function HitCard({ hit, index }: { hit: SearchHit; index: number }) {
  const score = Math.round(hit.score * 100);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
    >
      <Card className="hover:border-primary/30 hover:shadow-sm transition-all">
        <CardContent className="p-4 space-y-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2 flex-1 min-w-0">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 mt-0.5">
                <FileText className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm truncate">{hit.document_name}</p>
                <div className="flex flex-wrap items-center gap-2 mt-0.5">
                  {hit.page && (
                    <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                      <BookOpen className="h-3 w-3" /> p.{hit.page}
                    </span>
                  )}
                  {hit.section && (
                    <span className="text-xs text-muted-foreground truncate max-w-[200px]">§ {hit.section}</span>
                  )}
                  <span className="text-xs text-muted-foreground capitalize">
                    [{hit.retrievers.join(" + ")}]
                  </span>
                </div>
              </div>
            </div>
            <Badge
              variant="outline"
              className={`text-xs shrink-0 ${score >= 80 ? "border-emerald-300 text-emerald-600" : score >= 60 ? "border-blue-300 text-blue-600" : "border-amber-300 text-amber-600"}`}
            >
              {score}% match
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3 pl-10 italic">
            "{hit.snippet}"
          </p>
          <div className="pl-10 flex items-center gap-2">
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Hash className="h-3 w-3" />
              {hit.chunk_id.slice(0, 8)}…
            </span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [route, setRoute] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const fn = mode === "hybrid" ? hybridSearch : semanticSearch;
      const res = await fn(query, 12);
      setResults(res.results);
      setRoute(res.route);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Semantic Paper Search</h2>
          <p className="text-muted-foreground mt-1">
            Search the RAG knowledge base using natural language — results are real document chunks retrieved via {mode === "hybrid" ? "BM25 + Vector + Graph" : "Vector"} search.
          </p>
        </div>

        {/* External sources banner */}
        <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white shadow-sm">
              <Globe className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold">Search External Research Databases</p>
              <p className="text-xs text-muted-foreground">Access arXiv, PubMed, Semantic Scholar &amp; CORE</p>
            </div>
          </div>
          <Button size="sm" variant="outline" className="shrink-0 gap-1.5" asChild>
            <Link to="/external">External Sources <ArrowRight className="h-3.5 w-3.5" /></Link>
          </Button>
        </div>

        {/* Search form */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="e.g., How does attention work in transformer models?"
              className="pl-10 h-11"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="px-6" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
            Search
          </Button>
        </form>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <SlidersHorizontal className="h-4 w-4" /> Mode:
          </div>
          <Select value={mode} onValueChange={(v) => setMode(v as SearchMode)}>
            <SelectTrigger className="w-52 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hybrid">🔀 Hybrid (BM25 + Vector + Graph)</SelectItem>
              <SelectItem value="semantic">🔢 Semantic (Vector only)</SelectItem>
            </SelectContent>
          </Select>
          {results !== null && (
            <Badge variant="secondary" className="text-xs">
              {results.length} chunks · via {route}
            </Badge>
          )}
        </div>
      </motion.div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Results */}
      {!hasSearched ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <Search className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Search the knowledge base</h3>
          <p className="text-sm text-muted-foreground max-w-sm mb-4">
            Results come from your uploaded documents — real chunks with exact page and section references.
          </p>
          <p className="text-xs text-muted-foreground">
            No documents yet?{" "}
            <Link to="/upload" className="text-primary hover:underline font-medium">Upload papers →</Link>
            {" "}or{" "}
            <Link to="/external" className="text-primary hover:underline font-medium">Browse external sources →</Link>
          </p>
        </motion.div>
      ) : loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border bg-card p-4 animate-pulse">
              <div className="flex gap-3">
                <div className="h-8 w-8 rounded-lg bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-3/4 rounded bg-muted" />
                  <div className="h-3 w-full rounded bg-muted" />
                  <div className="h-3 w-5/6 rounded bg-muted" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : results !== null && results.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Search className="h-10 w-10 text-muted-foreground/40 mb-4" />
          <h3 className="font-semibold mb-1">No matching chunks found</h3>
          <p className="text-sm text-muted-foreground mb-3 max-w-sm">
            Try different keywords, or ingest more papers first.
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to="/upload"><ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Upload Papers</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to="/external"><Globe className="mr-1.5 h-3.5 w-3.5" /> External Sources</Link>
            </Button>
          </div>
        </div>
      ) : results !== null ? (
        <div className="space-y-3">
          {results.map((hit, i) => <HitCard key={hit.chunk_id} hit={hit} index={i} />)}
        </div>
      ) : null}
    </div>
  );
}
