import { useState } from "react";
import { motion } from "framer-motion";
import { Quote, Search, Copy, CheckCheck, BookOpen, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { mockPapers } from "@/data/mockPapers";

const citationFormats = {
  apa: (p: typeof mockPapers[0]) =>
    `${p.authors.join(", ")} (${p.year}). ${p.title}. *${p.venue}*. https://doi.org/${p.doi}`,
  mla: (p: typeof mockPapers[0]) =>
    `${p.authors[0]}, et al. "${p.title}." *${p.venue}*, ${p.year}.`,
  chicago: (p: typeof mockPapers[0]) =>
    `${p.authors.join(", ")}. "${p.title}." ${p.venue} (${p.year}). https://doi.org/${p.doi}.`,
  bibtex: (p: typeof mockPapers[0]) =>
    `@article{${p.id},\n  title={${p.title}},\n  author={${p.authors.join(" and ")}},\n  journal={${p.venue}},\n  year={${p.year}},\n  doi={${p.doi}}\n}`,
};

export default function CitationPage() {
  const [query, setQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [format, setFormat] = useState<keyof typeof citationFormats>("apa");

  const recommendations = mockPapers.slice(0, 8).map((p, i) => ({
    ...p,
    relevanceScore: Math.max(0.65, p.similarityScore - i * 0.03),
  }));

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setHasSearched(true);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="text-2xl font-bold tracking-tight">Citation Recommendations</h2>
        <p className="text-muted-foreground mt-1">
          Enter a paper title or paste an abstract to get intelligent citation suggestions.
        </p>
      </motion.div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Enter paper title or abstract to find relevant citations..."
            className="pl-10 h-11"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" size="lg">
          <Quote className="mr-2 h-4 w-4" /> Find Citations
        </Button>
      </form>

      {!hasSearched ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-20 text-center"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <Quote className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Find relevant citations</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Our AI analyzes your paper's content and recommends the most relevant citations based on semantic similarity.
          </p>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Format Selector */}
          <Tabs value={format} onValueChange={(v) => setFormat(v as keyof typeof citationFormats)}>
            <div className="flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="apa">APA</TabsTrigger>
                <TabsTrigger value="mla">MLA</TabsTrigger>
                <TabsTrigger value="chicago">Chicago</TabsTrigger>
                <TabsTrigger value="bibtex">BibTeX</TabsTrigger>
              </TabsList>
              <Badge variant="secondary">{recommendations.length} recommendations</Badge>
            </div>

            {Object.keys(citationFormats).map((fmt) => (
              <TabsContent key={fmt} value={fmt} className="space-y-3 mt-4">
                {recommendations.map((paper, i) => {
                  const citation = citationFormats[fmt as keyof typeof citationFormats](paper);
                  return (
                    <motion.div
                      key={paper.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                    >
                      <Card className="hover:shadow-sm transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-3 mb-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-semibold line-clamp-1">{paper.title}</h4>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {paper.authors.slice(0, 3).join(", ")} · {paper.year} · {paper.venue}
                              </p>
                            </div>
                            <Badge
                              variant={paper.relevanceScore >= 0.85 ? "default" : "secondary"}
                              className="shrink-0 text-xs"
                            >
                              {(paper.relevanceScore * 100).toFixed(0)}% relevant
                            </Badge>
                          </div>

                          <div className="rounded-lg bg-muted/50 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
                            {citation}
                          </div>

                          <div className="flex items-center justify-end gap-2 mt-3">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs gap-1.5"
                              onClick={() => handleCopy(paper.id + fmt, citation)}
                            >
                              {copiedId === paper.id + fmt ? (
                                <><CheckCheck className="h-3 w-3 text-emerald-500" /> Copied</>
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
            ))}
          </Tabs>
        </motion.div>
      )}
    </div>
  );
}
