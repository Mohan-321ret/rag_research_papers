import { useParams, Link } from "react-router-dom";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Calendar,
  Hash,
  Copy,
  CheckCheck,
  Loader2,
  AlertCircle,
  BookOpen,
  Layers,
  Database,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { fetchDocuments, hybridSearch, type DocumentRead, type SearchHit } from "@/lib/api";

export default function PaperDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [chunks, setChunks] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);

    // Fetch the document by listing and finding it
    fetchDocuments({ limit: 200 })
      .then(async (res) => {
        const found = res.items.find((d) => d.id === id) ?? res.items[0] ?? null;
        setDoc(found);
        if (found) {
          // Search for chunks from this document
          try {
            const searchRes = await hybridSearch(found.title, 8);
            setChunks(searchRes.results.filter((h) => h.document_id === found.id || h.document_name === found.title));
          } catch { /* non-fatal */ }
        }
        setLoading(false);
      })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [id]);

  const handleCopyCitation = () => {
    if (!doc) return;
    const citation = `${doc.title} (${new Date(doc.created_at).getFullYear()}). [${doc.source_type}]. Knowledge Base Document ID: ${doc.id}`;
    navigator.clipboard.writeText(citation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) return (
    <div className="p-6 flex items-center justify-center min-h-[60vh]">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );

  if (error || !doc) return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <Button variant="ghost" size="sm" asChild><Link to="/search"><ArrowLeft className="mr-2 h-4 w-4" /> Back</Link></Button>
      <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" /> {error ?? "Document not found."}
      </div>
    </div>
  );

  const metadata = doc.metadata as Record<string, unknown>;
  const sourceUrl = metadata?.source_url as string | undefined;
  const pdfUrl = metadata?.pdf_url as string | undefined;
  const authors = metadata?.authors as string[] | undefined;
  const abstract = metadata?.abstract as string | undefined;
  const keywords = metadata?.keywords as string[] | undefined;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link to="/search"><ArrowLeft className="mr-2 h-4 w-4" /> Back to Search</Link>
      </Button>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-6">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="capitalize">{doc.source_type}</Badge>
            <Badge variant="outline">{new Date(doc.created_at).getFullYear()}</Badge>
            <Badge
              variant="outline"
              className={`${doc.status === "ready" ? "border-emerald-300 text-emerald-600" : ""}`}
            >
              {doc.status}
            </Badge>
            {doc.current_version && (
              <Badge variant="outline">v{doc.current_version}</Badge>
            )}
          </div>

          <h1 className="text-2xl md:text-3xl font-bold tracking-tight leading-tight">{doc.title}</h1>

          {authors && authors.length > 0 && (
            <p className="text-sm text-muted-foreground">{authors.join(", ")}</p>
          )}

          <div className="flex flex-wrap gap-2">
            {pdfUrl && (
              <Button size="sm" className="gap-1.5" asChild>
                <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-3.5 w-3.5" /> View PDF
                </a>
              </Button>
            )}
            {sourceUrl && (
              <Button size="sm" variant="outline" className="gap-1.5" asChild>
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                  <FileText className="h-3.5 w-3.5" /> Source
                </a>
              </Button>
            )}
            <Button size="sm" variant="outline" className="gap-1.5" onClick={handleCopyCitation}>
              {copied ? <CheckCheck className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied!" : "Copy Citation"}
            </Button>
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Abstract */}
            {abstract && (
              <Card>
                <CardHeader><CardTitle className="text-base">Abstract</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">{abstract}</p>
                </CardContent>
              </Card>
            )}

            {/* RAG Chunks from this document */}
            {chunks.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <BookOpen className="h-4 w-4" /> Indexed Chunks ({chunks.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {chunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="rounded-lg border bg-muted/30 p-3 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {chunk.page && <span className="flex items-center gap-0.5"><BookOpen className="h-3 w-3" /> p.{chunk.page}</span>}
                          {chunk.section && <span>§ {chunk.section}</span>}
                          <span className="flex items-center gap-0.5"><Hash className="h-3 w-3" />{chunk.chunk_id.slice(0, 8)}</span>
                        </div>
                        <Badge variant="outline" className="text-xs">{Math.round(chunk.score * 100)}%</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground italic">"{chunk.snippet}"</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Metadata */}
            <Card>
              <CardHeader><CardTitle className="text-base">Document Details</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Document ID</p>
                  <p className="font-mono text-xs break-all text-primary">{doc.id}</p>
                </div>
                <Separator />
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Ingested</p>
                    <p className="font-medium">{new Date(doc.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Versions</p>
                    <p className="font-medium">{doc.version_count}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Source</p>
                    <p className="font-medium capitalize">{doc.source_type}</p>
                  </div>
                </div>
                {keywords && keywords.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <p className="text-xs text-muted-foreground mb-1.5">Keywords</p>
                      <div className="flex flex-wrap gap-1.5">
                        {keywords.map((kw) => <Badge key={kw} variant="outline" className="text-xs">{kw}</Badge>)}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
