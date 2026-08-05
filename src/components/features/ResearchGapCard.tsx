import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { AlertTriangle, ArrowRight, BookOpen, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ResearchGap } from "@/data/mockGaps";
import { cn } from "@/lib/utils";

interface ResearchGapCardProps {
  gap: ResearchGap;
  index?: number;
}

export function ResearchGapCard({ gap, index = 0 }: ResearchGapCardProps) {
  const severityConfig = {
    high: { color: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950/30", label: "High Priority" },
    medium: { color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950/30", label: "Medium Priority" },
    low: { color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950/30", label: "Low Priority" },
  };

  const sev = severityConfig[gap.severity];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
    >
      <Card className="hover:shadow-md transition-all duration-200">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn("text-xs", sev.color)}>
                  <AlertTriangle className="mr-1 h-3 w-3" />
                  {sev.label}
                </Badge>
                <Badge variant="secondary" className="text-xs">{gap.domain}</Badge>
              </div>
              <CardTitle className="text-base leading-snug">{gap.title}</CardTitle>
            </div>
            <div className="text-right shrink-0">
              <div className="text-2xl font-bold text-primary">{gap.confidence}%</div>
              <div className="text-xs text-muted-foreground">confidence</div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground leading-relaxed">{gap.description}</p>

          {/* Confidence bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Detection Confidence</span>
              <span className="font-medium">{gap.confidence}%</span>
            </div>
            <Progress value={gap.confidence} />
          </div>

          {/* Evidence */}
          <div className="space-y-2">
            <h4 className="flex items-center gap-1.5 text-sm font-medium">
              <BookOpen className="h-3.5 w-3.5 text-primary" />
              Evidence ({gap.evidence.length})
            </h4>
            <ul className="space-y-1.5">
              {gap.evidence.map((ev, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary/40 shrink-0" />
                  {ev}
                </li>
              ))}
            </ul>
          </div>

          {/* Future Directions */}
          <div className="space-y-2">
            <h4 className="flex items-center gap-1.5 text-sm font-medium">
              <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
              Future Research Directions
            </h4>
            <ul className="space-y-1.5">
              {gap.futureDirections.map((dir, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 text-primary/60 shrink-0" />
                  {dir}
                </li>
              ))}
            </ul>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-xs text-muted-foreground">
              {gap.relatedPaperCount} related papers analyzed
            </span>
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              Explore Gap
              <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
