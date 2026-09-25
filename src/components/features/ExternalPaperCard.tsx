import { motion } from "framer-motion";
import { ExternalLink, FileText, BookOpen, FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  type ExternalPaper,
  getSourceMeta,
  buildPaperUrl,
  buildPdfUrl,
} from "@/lib/externalApi";
import { cn } from "@/lib/utils";

interface ExternalPaperCardProps {
  paper: ExternalPaper;
  index?: number;
  onIngest?: (paper: ExternalPaper) => void;
  isIngesting?: boolean;
}

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  arxiv: <FileText className="h-3.5 w-3.5" />,
  pubmed: <FlaskConical className="h-3.5 w-3.5" />,
  semantic_scholar: <BookOpen className="h-3.5 w-3.5" />,
};

export function ExternalPaperCard({
  paper,
  index = 0,
  onIngest,
  isIngesting,
}: ExternalPaperCardProps) {
  const meta = getSourceMeta(paper.source);
  const paperUrl = buildPaperUrl(paper);
  const pdfUrl = buildPdfUrl(paper);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <Card className="group hover:border-primary/40 hover:shadow-md transition-all duration-200">
        <CardContent className="p-4 space-y-3">
          {/* Source + date badge row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                meta.bgClass,
                meta.textClass
              )}
            >
              {SOURCE_ICONS[paper.source] ?? meta.icon}
              {meta.label}
            </span>
            {paper.published && (
              <Badge variant="outline" className="text-xs">
                {paper.published}
              </Badge>
            )}
            {paper.doi && (
              <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                DOI: {paper.doi}
              </span>
            )}
          </div>

          {/* Title */}
          <a
            href={paperUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="block group-hover:text-primary transition-colors"
          >
            <h3 className="font-semibold text-sm leading-snug line-clamp-2">
              {paper.title}
            </h3>
          </a>

          {/* Authors */}
          {paper.authors && (
            <p className="text-xs text-muted-foreground line-clamp-1">
              {paper.authors}
            </p>
          )}

          {/* Abstract */}
          {paper.abstract && (
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
              {paper.abstract}
            </p>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" asChild>
              <a href={paperUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3 w-3" />
                View on {meta.label}
              </a>
            </Button>

            {pdfUrl && (
              <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" asChild>
                <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
                  <FileText className="h-3 w-3" />
                  PDF
                </a>
              </Button>
            )}

            {onIngest && (
              <Button
                size="sm"
                className="h-7 text-xs gap-1.5 ml-auto"
                onClick={() => onIngest(paper)}
                disabled={isIngesting}
              >
                {isIngesting ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                      className="h-3 w-3 border-2 border-current/30 border-t-current rounded-full"
                    />
                    Adding…
                  </>
                ) : (
                  <>+ Add to Knowledge Base</>
                )}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
