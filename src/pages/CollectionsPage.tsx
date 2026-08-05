import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { mockPapers } from "@/data/mockPapers";

interface Collection {
  id: string;
  name: string;
  description: string;
  paperCount: number;
  color: string;
  papers: typeof mockPapers;
}

const initialCollections: Collection[] = [
  {
    id: "col1",
    name: "RAG Pipeline Research",
    description: "Papers related to retrieval-augmented generation",
    paperCount: 5,
    color: "bg-violet-500",
    papers: mockPapers.slice(0, 5),
  },
  {
    id: "col2",
    name: "Transformer Architectures",
    description: "Foundation models and attention mechanisms",
    paperCount: 4,
    color: "bg-blue-500",
    papers: mockPapers.slice(3, 7),
  },
  {
    id: "col3",
    name: "Embedding Methods",
    description: "Sentence embeddings and dense retrieval",
    paperCount: 3,
    color: "bg-emerald-500",
    papers: mockPapers.slice(1, 4),
  },
  {
    id: "col4",
    name: "Evaluation & Benchmarks",
    description: "Metrics and evaluation frameworks",
    paperCount: 2,
    color: "bg-amber-500",
    papers: mockPapers.slice(10, 12),
  },
];

export default function CollectionsPage() {
  const navigate = useNavigate();
  const [collections] = useState<Collection[]>(initialCollections);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Saved Papers & Collections</h2>
          <p className="text-muted-foreground mt-1">
            Organize your research papers into collections for easy access.
          </p>
        </div>
        <Button className="gap-2">
          <Plus className="h-4 w-4" /> New Collection
        </Button>
      </motion.div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search collections and papers..."
          className="pl-10"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {selectedCollection ? (
        /* Collection Detail */
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="space-y-4"
        >
          <Button variant="ghost" size="sm" onClick={() => setSelectedCollection(null)}>
            ← Back to Collections
          </Button>

          <div className="flex items-center gap-3">
            <div className={`h-10 w-10 rounded-lg ${selectedCollection.color} flex items-center justify-center text-white`}>
              <FolderOpen className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xl font-semibold">{selectedCollection.name}</h3>
              <p className="text-sm text-muted-foreground">{selectedCollection.description}</p>
            </div>
            <Badge variant="secondary" className="ml-auto">{selectedCollection.paperCount} papers</Badge>
          </div>

          <div className="space-y-3">
            {selectedCollection.papers.map((paper, i) => (
              <motion.div
                key={paper.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="hover:shadow-sm transition-shadow cursor-pointer" onClick={() => navigate(`/paper/${paper.id}`)}>
                  <CardContent className="p-4 flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 shrink-0">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold line-clamp-1">{paper.title}</h4>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {paper.authors[0]} et al. · {paper.year} · {paper.venue}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{paper.abstract}</p>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0">
                      {(paper.similarityScore * 100).toFixed(0)}%
                    </Badge>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>
      ) : (
        /* Collections Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((collection, i) => (
            <motion.div
              key={collection.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.08 }}
            >
              <Card
                className="group hover:shadow-md transition-all duration-200 cursor-pointer hover:border-primary/30"
                onClick={() => setSelectedCollection(collection)}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className={`h-10 w-10 rounded-lg ${collection.color} flex items-center justify-center text-white`}>
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
                  <h3 className="font-semibold mb-1 group-hover:text-primary transition-colors">
                    {collection.name}
                  </h3>
                  <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                    {collection.description}
                  </p>
                  <div className="flex items-center gap-2">
                    <BookMarked className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">{collection.paperCount} papers</span>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}

          {/* Add Collection Card */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: collections.length * 0.08 }}
          >
            <Card className="h-full border-dashed hover:border-primary/50 hover:bg-muted/30 transition-all cursor-pointer flex items-center justify-center min-h-[180px]">
              <CardContent className="flex flex-col items-center text-center p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted mb-3">
                  <Plus className="h-5 w-5 text-muted-foreground" />
                </div>
                <p className="text-sm font-medium text-muted-foreground">Create New Collection</p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
