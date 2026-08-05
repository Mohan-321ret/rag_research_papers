import { useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ExternalLink,
  Bookmark,
  FileText,
  Quote,
  Calendar,
  Building2,
  Hash,
  Users,
  Copy,
  CheckCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { mockPapers } from "@/data/mockPapers";
import { useState } from "react";

export default function PaperDetailPage() {
  const { id } = useParams();
  const paper = mockPapers.find((p) => p.id === id) || mockPapers[0]!;
  const relatedPapers = mockPapers.filter((p) => p.id !== paper.id).slice(0, 4);
  const [copied, setCopied] = useState(false);

  const handleCopyCitation = () => {
    const citation = `${paper.authors.join(", ")} (${paper.year}). ${paper.title}. ${paper.venue}. DOI: ${paper.doi}`;
    navigator.clipboard.writeText(citation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Back Button */}
      <Button variant="ghost" size="sm" asChild>
        <Link to="/search">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Search
        </Link>
      </Button>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="space-y-6"
      >
        {/* Header */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{paper.venue}</Badge>
            <Badge variant="outline">{paper.year}</Badge>
            <Badge variant="success">
              {(paper.similarityScore * 100).toFixed(0)}% match
            </Badge>
          </div>

          <h1 className="text-2xl md:text-3xl font-bold tracking-tight leading-tight">
            {paper.title}
          </h1>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Users className="h-4 w-4" />
              {paper.authors.join(", ")}
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              {paper.year}
            </span>
            <span className="flex items-center gap-1.5">
              <Building2 className="h-4 w-4" />
              {paper.venue}
            </span>
            <span className="flex items-center gap-1.5">
              <Quote className="h-4 w-4" />
              {paper.citationCount.toLocaleString()} citations
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" className="gap-1.5">
              <ExternalLink className="h-3.5 w-3.5" /> View PDF
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5">
              <Bookmark className="h-3.5 w-3.5" /> Save to Collection
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5" onClick={handleCopyCitation}>
              {copied ? <CheckCheck className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied!" : "Copy Citation"}
            </Button>
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Abstract */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Abstract</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-muted-foreground">{paper.abstract}</p>
              </CardContent>
            </Card>

            {/* Key Findings (mock) */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Key Findings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  "The proposed approach achieves state-of-the-art results on multiple benchmark datasets.",
                  "Ablation studies confirm that each component contributes significantly to overall performance.",
                  "The method scales efficiently to large-scale datasets with minimal computational overhead.",
                  "Human evaluation confirms strong alignment with expert assessments.",
                ].map((finding, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                    {finding}
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Citation Graph Placeholder */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Citation Network</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-48 rounded-lg bg-muted/50 flex items-center justify-center border border-dashed">
                  <div className="text-center text-muted-foreground">
                    <Hash className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm font-medium">Citation Graph Visualization</p>
                    <p className="text-xs">Interactive network will be available when backend is connected</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Metadata */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-xs text-muted-foreground">DOI</p>
                  <p className="text-sm font-medium text-primary">{paper.doi}</p>
                </div>
                <Separator />
                <div>
                  <p className="text-xs text-muted-foreground">Keywords</p>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {paper.keywords.map((kw) => (
                      <Badge key={kw} variant="outline" className="text-xs">{kw}</Badge>
                    ))}
                  </div>
                </div>
                <Separator />
                <div>
                  <p className="text-xs text-muted-foreground">Similarity Score</p>
                  <p className="text-2xl font-bold text-primary">{(paper.similarityScore * 100).toFixed(0)}%</p>
                </div>
              </CardContent>
            </Card>

            {/* Related Papers */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Related Papers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {relatedPapers.map((rp) => (
                  <Link key={rp.id} to={`/paper/${rp.id}`} className="block group">
                    <div className="space-y-1 py-2 border-b last:border-0">
                      <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-2">
                        {rp.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {rp.authors[0]} · {rp.year}
                      </p>
                    </div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
