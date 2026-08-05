import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, SlidersHorizontal, ArrowUpDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PaperCard } from "@/components/features/PaperCard";
import { mockPapers } from "@/data/mockPapers";

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState("relevance");
  const [yearFilter, setYearFilter] = useState("all");
  const [hasSearched, setHasSearched] = useState(false);

  const filteredPapers = useMemo(() => {
    let papers = [...mockPapers];
    if (yearFilter !== "all") {
      const year = parseInt(yearFilter);
      papers = papers.filter((p) => p.year >= year);
    }
    if (sortBy === "relevance") papers.sort((a, b) => b.similarityScore - a.similarityScore);
    else if (sortBy === "year") papers.sort((a, b) => b.year - a.year);
    else if (sortBy === "citations") papers.sort((a, b) => b.citationCount - a.citationCount);
    return papers;
  }, [sortBy, yearFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setHasSearched(true);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Search Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-4"
      >
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Semantic Paper Search</h2>
          <p className="text-muted-foreground mt-1">
            Search using natural language. Our transformer embeddings find papers by meaning, not just keywords.
          </p>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="e.g., How does retrieval-augmented generation improve factual accuracy?"
              className="pl-10 h-11"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="px-6">
            <Search className="mr-2 h-4 w-4" />
            Search
          </Button>
        </form>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <SlidersHorizontal className="h-4 w-4" />
            Filters:
          </div>
          <Select value={yearFilter} onValueChange={setYearFilter}>
            <SelectTrigger className="w-36 h-8">
              <SelectValue placeholder="Year" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Years</SelectItem>
              <SelectItem value="2024">2024+</SelectItem>
              <SelectItem value="2023">2023+</SelectItem>
              <SelectItem value="2022">2022+</SelectItem>
              <SelectItem value="2020">2020+</SelectItem>
              <SelectItem value="2018">2018+</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-40 h-8">
              <ArrowUpDown className="mr-1.5 h-3 w-3" />
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="relevance">Relevance</SelectItem>
              <SelectItem value="year">Newest First</SelectItem>
              <SelectItem value="citations">Most Cited</SelectItem>
            </SelectContent>
          </Select>
          {hasSearched && (
            <Badge variant="secondary" className="text-xs">
              {filteredPapers.length} results
            </Badge>
          )}
        </div>
      </motion.div>

      {/* Results */}
      {!hasSearched ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-20 text-center"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <Search className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Search the knowledge base</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Enter a query above to find semantically similar papers using transformer-based embeddings.
          </p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredPapers.map((paper, i) => (
            <PaperCard
              key={paper.id}
              paper={paper}
              index={i}
              onView={(id) => navigate(`/paper/${id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
