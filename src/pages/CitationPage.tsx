import { useState } from "react";
import { motion } from "framer-motion";
import {
  Quote,
  Search,
  Copy,
  CheckCheck,
  Loader2,
  AlertCircle,
  FileText,
  BookOpen,
  Zap,
  Hash,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { hybridSearch, type SearchHit } from "@/lib/api";

type CiteFormat = "apa" | "mla" | "chicago" | "bibtex";

function formatCitation(hit: SearchHit, fmt: CiteFormat): string {
  // Best-effort citation from what the RAG chunk gives us
  const title = hit.document_name;
  const year = new Date().getFullYear(); // unknown from chunk — use current year as placeholder
  const source = hit.section ?? "Research Document";
  const id = hit.chunk_id.slice(0, 8);
  const page = hit.page ? `, p. ${hit.page}` : "";

  switch (fmt) {
    case "apa":
      return `Author(s). (${year}). ${title}${source !== "Research Document" ? `: ${source}` : ""}${page}. [RAG Knowledge Base].`;
    case "mla":
      return `"${source !== "Research Document" ? source : title}." ${title}, ${year}${page}.`;
    case "chicago":
      return `Author(s). "${source !== "Research Document" ? source : title}." ${title} (${year})${page}.`;
    case "bibtex":
      return `@misc{${id},\n  title={${title}},\n  year={${year}},\n  note={${source}${page}},\n  howpublished={RAG Knowledge Base}\n}`;
  }
}

export default function CitationPage() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [format, setFormat] = useState<CiteFormat>("apa");

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await hybridSearch(query, 10);
      setHits(res.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold tracking-tight">Citation Generator</h2>
        <p className="text-muted-foreground mt-1">
          Search the RAG knowledge base and generate citations for relevant document chunks.
        </p>
      </motion.div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="e.g., attention mechanism, transformer self-attention, BERT embeddings…"
            className="pl-10 h-11"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" size="lg" disabled={loading}>
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Quote className="mr-2 h-4 w-4" />}
          Find & Cite
        </Button>
      </form>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Empty state */}
      {!hits && !loading && !error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <Quote className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Find relevant document sources</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Enter a topic to search your knowledge base. Matching document chunks are instantly formatted as citations.
          </p>
        </motion.div>
      )}

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border bg-card p-4 animate-pulse">
              <div className="h-16 bg-muted rounded" />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {hits !== null && !loading && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <Tabs value={format} onValueChange={(v) => setFormat(v as CiteFormat)}>
            <div className="flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="apa">APA</TabsTrigger>
                <TabsTrigger value="mla">MLA</TabsTrigger>
                <TabsTrigger value="chicago">Chicago</TabsTrigger>
                <TabsTrigger value="bibtex">BibTeX</TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">{hits.length} sources found</Badge>
                <Badge variant="outline" className="text-xs flex items-center gap-1">
                  <Zap className="h-3 w-3 text-emerald-500" /> RAG Search
                </Badge>
              </div>
            </div>

            {hits.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Search className="h-8 w-8 text-muted-foreground/40 mb-3" />
                <p className="font-semibold">No matching documents</p>
                <p className="text-sm text-muted-foreground mt-1">Try different keywords or upload more papers.</p>
              </div>
            ) : (
              (["apa", "mla", "chicago", "bibtex"] as CiteFormat[]).map((fmt) => (
                <TabsContent key={fmt} value={fmt} className="space-y-3 mt-4">
                  {hits.map((hit, i) => {
                    const citation = formatCitation(hit, fmt);
                    const copyKey = hit.chunk_id + fmt;
                    return (
                      <motion.div
                        key={hit.chunk_id}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                      >
                        <Card className="hover:shadow-sm transition-shadow">
                          <CardContent className="p-4 space-y-3">
                            {/* Header */}
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-start gap-2 flex-1 min-w-0">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 mt-0.5">
                                  <FileText className="h-4 w-4 text-primary" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-semibold truncate">{hit.document_name}</p>
                                  <div className="flex flex-wrap gap-2 mt-0.5">
                                    {hit.page && (
                                      <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                                        <BookOpen className="h-3 w-3" /> p.{hit.page}
                                      </span>
                                    )}
                                    {hit.section && (
                                      <span className="text-xs text-muted-foreground">§ {hit.section}</span>
                                    )}
                                    <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                                      <Hash className="h-3 w-3" />{hit.chunk_id.slice(0, 8)}
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <Badge
                                variant="outline"
                                className={`text-xs shrink-0 ${hit.score >= 0.8 ? "border-emerald-300 text-emerald-600" : "border-blue-300 text-blue-600"}`}
                              >
                                {Math.round(hit.score * 100)}%
                              </Badge>
                            </div>

                            {/* Snippet */}
                            <p className="text-xs text-muted-foreground italic line-clamp-2">"{hit.snippet}"</p>

                            {/* Citation box */}
                            <div className="rounded-lg bg-muted/50 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
                              {citation}
                            </div>

                            <div className="flex justify-end">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs gap-1.5"
                                onClick={() => handleCopy(copyKey, citation)}
                              >
                                {copiedId === copyKey ? (
                                  <><CheckCheck className="h-3 w-3 text-emerald-500" /> Copied!</>
                                ) : (
                                  <><Copy className="h-3 w-3" /> Copy</>
                                )}
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    );
                  })}
                </TabsContent>
              ))
            )}
          </Tabs>
        </motion.div>
      )}
    </div>
  );
}
