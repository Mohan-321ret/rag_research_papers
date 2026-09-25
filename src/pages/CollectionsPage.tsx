import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  FolderOpen,
  MoreHorizontal,
  Search,
  FileText,
  Trash2,
  Edit3,
  BookMarked,
  Loader2,
  AlertCircle,
  Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchDocuments, type DocumentRead } from "@/lib/api";

const COLORS = [
  "bg-violet-500",
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-indigo-500",
];

// Group documents into pseudo-collections by source_type
function groupDocs(docs: DocumentRead[]) {
  const groups: Record<string, DocumentRead[]> = {};
  for (const doc of docs) {
    const key = doc.source_type || "manual";
    if (!groups[key]) groups[key] = [];
    groups[key]!.push(doc);
  }
  return Object.entries(groups).map(([type, items], i) => ({
    id: type,
    name: type === "manual" ? "Uploaded Papers" : type === "arxiv" ? "arXiv Papers" : type === "pubmed" ? "PubMed Papers" : type.charAt(0).toUpperCase() + type.slice(1),
    description: `${items.length} document${items.length !== 1 ? "s" : ""} from ${type}`,
    color: COLORS[i % COLORS.length]!,
    papers: items,
  }));
}

export default function CollectionsPage() {
  const [docs, setDocs] = useState<DocumentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ReturnType<typeof groupDocs>[0] | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchDocuments({ limit: 100 })
      .then((res) => { setDocs(res.items); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const collections = groupDocs(docs);
  const filtered = collections.filter((c) =>
    !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Knowledge Base Collections</h2>
          <p className="text-muted-foreground mt-1">Your documents organized by source type.</p>
        </div>
        <Button asChild className="gap-2">
          <Link to="/upload"><Plus className="h-4 w-4" /> Add Documents</Link>
        </Button>
      </motion.div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search collections…"
          className="pl-10"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}><CardContent className="p-5 animate-pulse"><div className="h-28 bg-muted rounded" /></CardContent></Card>
          ))}
        </div>
      )}

      {!loading && selected ? (
        /* ── Collection detail ─────────────────────────────────────── */
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>← Back to Collections</Button>
          <div className="flex items-center gap-3">
            <div className={`h-10 w-10 rounded-lg ${selected.color} flex items-center justify-center text-white`}>
              <FolderOpen className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xl font-semibold">{selected.name}</h3>
              <p className="text-sm text-muted-foreground">{selected.description}</p>
            </div>
            <Badge variant="secondary" className="ml-auto">{selected.papers.length} documents</Badge>
          </div>

          <div className="space-y-3">
            {selected.papers.map((doc, i) => (
              <motion.div key={doc.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Card className="hover:shadow-sm transition-shadow">
                  <CardContent className="p-4 flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 shrink-0">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold line-clamp-1">{doc.title}</h4>
                      <p className="text-xs text-muted-foreground mt-0.5 capitalize">
                        {doc.source_type} · v{doc.current_version ?? 1} · {new Date(doc.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-xs shrink-0 ${doc.status === "ready" ? "border-emerald-300 text-emerald-600" : ""}`}
                    >
                      {doc.status}
                    </Badge>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>
      ) : !loading && (
        /* ── Collections grid ──────────────────────────────────────── */
        filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
              <Upload className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-2">No documents yet</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-sm">
              Upload papers or import from external sources to build your knowledge base.
            </p>
            <div className="flex gap-2">
              <Button asChild><Link to="/upload">Upload Papers</Link></Button>
              <Button variant="outline" asChild><Link to="/external">Browse External</Link></Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((col, i) => (
              <motion.div
                key={col.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.08 }}
              >
                <Card
                  className="group hover:shadow-md transition-all duration-200 cursor-pointer hover:border-primary/30"
                  onClick={() => setSelected(col)}
                >
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className={`h-10 w-10 rounded-lg ${col.color} flex items-center justify-center text-white`}>
                        <FolderOpen className="h-5 w-5" />
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem><Edit3 className="mr-2 h-4 w-4" /> Rename</DropdownMenuItem>
                          <DropdownMenuItem className="text-destructive"><Trash2 className="mr-2 h-4 w-4" /> Delete</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <h3 className="font-semibold mb-1 group-hover:text-primary transition-colors">{col.name}</h3>
                    <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{col.description}</p>
                    <div className="flex items-center gap-2">
                      <BookMarked className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">{col.papers.length} documents</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}

            {/* Add new */}
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: filtered.length * 0.08 }}>
              <Link to="/upload">
                <Card className="h-full border-dashed hover:border-primary/50 hover:bg-muted/30 transition-all cursor-pointer flex items-center justify-center min-h-[180px]">
                  <CardContent className="flex flex-col items-center text-center p-5">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted mb-3">
                      <Plus className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <p className="text-sm font-medium text-muted-foreground">Add More Documents</p>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          </div>
        )
      )}
    </div>
  );
}
