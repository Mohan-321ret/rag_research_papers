import { motion } from "framer-motion";
import { FileText, Bookmark, BookmarkCheck, ExternalLink, Quote } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Paper } from "@/data/mockPapers";
import { cn } from "@/lib/utils";

interface PaperCardProps {
  paper: Paper;
  index?: number;
  onSave?: (id: string) => void;
  onCite?: (paper: Paper) => void;
  onView?: (id: string) => void;
}

export function PaperCard({ paper, index = 0, onSave, onCite, onView }: PaperCardProps) {
  const scoreColor =
    paper.similarityScore >= 0.9
      ? "text-emerald-600 dark:text-emerald-400"
      : paper.similarityScore >= 0.8
      ? "text-blue-600 dark:text-blue-400"
      : "text-amber-600 dark:text-amber-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <Card className="group hover:shadow-md transition-all duration-200 hover:border-primary/30">
        <CardContent className="p-5">
          {/* Header row */}
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary" className="font-normal">
                {paper.venue}
              </Badge>
              <span>{paper.year}</span>
            </div>
            <div className={cn("flex items-center gap-1 text-sm font-semibold", scoreColor)}>
              {(paper.similarityScore * 100).toFixed(0)}%
              <span className="text-xs font-normal text-muted-foreground">match</span>
            </div>
          </div>

          {/* Title */}
          <h3
            className="text-base font-semibold leading-snug mb-2 group-hover:text-primary transition-colors cursor-pointer line-clamp-2"
            onClick={() => onView?.(paper.id)}
          >
            {paper.title}
          </h3>

          {/* Authors */}
          <p className="text-sm text-muted-foreground mb-3 line-clamp-1">
            {paper.authors.join(", ")}
          </p>

          {/* Abstract */}
          <p className="text-sm text-muted-foreground/80 mb-4 line-clamp-3 leading-relaxed">
            {paper.abstract}
          </p>

          {/* Keywords */}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {paper.keywords.slice(0, 4).map((kw) => (
              <Badge key={kw} variant="outline" className="text-xs font-normal py-0">
                {kw}
              </Badge>
            ))}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between pt-3 border-t">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Quote className="h-3 w-3" />
              <span>{paper.citationCount.toLocaleString()} citations</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => onView?.(paper.id)}
              >
                <ExternalLink className="h-3 w-3" />
                View PDF
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => onSave?.(paper.id)}
              >
                {paper.saved ? (
                  <BookmarkCheck className="h-3 w-3 text-primary" />
                ) : (
                  <Bookmark className="h-3 w-3" />
                )}
                {paper.saved ? "Saved" : "Save"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => onCite?.(paper)}
              >
                <FileText className="h-3 w-3" />
                Cite
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
