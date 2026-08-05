import { motion } from "framer-motion";
import { mockHeatmapData } from "@/data/mockGaps";
import { cn } from "@/lib/utils";

export function CoverageHeatmap() {
  const topics = [...new Set(mockHeatmapData.map((d) => d.topic))];
  const subtopics = [...new Set(mockHeatmapData.map((d) => d.subtopic))];

  const getCell = (topic: string, subtopic: string) =>
    mockHeatmapData.find((d) => d.topic === topic && d.subtopic === subtopic);

  const getCoverageColor = (coverage: number) => {
    if (coverage >= 80) return "bg-emerald-500/80 dark:bg-emerald-500/60";
    if (coverage >= 60) return "bg-emerald-400/60 dark:bg-emerald-400/40";
    if (coverage >= 40) return "bg-amber-400/60 dark:bg-amber-400/40";
    if (coverage >= 20) return "bg-orange-400/60 dark:bg-orange-400/40";
    return "bg-red-400/60 dark:bg-red-400/40";
  };

  return (
    <div className="w-full rounded-xl border bg-card p-4 overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-muted-foreground p-2" />
            {subtopics.map((st) => (
              <th key={st} className="text-center text-xs font-medium text-muted-foreground p-2">
                {st}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {topics.map((topic, ti) => (
            <tr key={topic}>
              <td className="text-xs font-medium text-muted-foreground p-2 whitespace-nowrap">{topic}</td>
              {subtopics.map((subtopic, si) => {
                const cell = getCell(topic, subtopic);
                return (
                  <td key={subtopic} className="p-1">
                    <motion.div
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.3, delay: (ti * subtopics.length + si) * 0.03 }}
                      className={cn(
                        "flex items-center justify-center rounded-md h-12 w-full min-w-[60px] text-xs font-semibold text-white cursor-default transition-transform hover:scale-105",
                        cell ? getCoverageColor(cell.coverage) : "bg-muted"
                      )}
                      title={cell ? `${topic} → ${subtopic}: ${cell.coverage}% coverage` : "No data"}
                    >
                      {cell ? `${cell.coverage}%` : "—"}
                    </motion.div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      
      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-muted-foreground">
        <span>Coverage:</span>
        <span className="flex items-center gap-1"><span className="h-3 w-6 rounded bg-red-400/60" /> Low (&lt;20%)</span>
        <span className="flex items-center gap-1"><span className="h-3 w-6 rounded bg-orange-400/60" /> 20–40%</span>
        <span className="flex items-center gap-1"><span className="h-3 w-6 rounded bg-amber-400/60" /> 40–60%</span>
        <span className="flex items-center gap-1"><span className="h-3 w-6 rounded bg-emerald-400/60" /> 60–80%</span>
        <span className="flex items-center gap-1"><span className="h-3 w-6 rounded bg-emerald-500/80" /> High (&gt;80%)</span>
      </div>
    </div>
  );
}
