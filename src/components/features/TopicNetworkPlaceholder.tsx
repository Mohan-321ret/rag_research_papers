import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { topicNetworkNodes, topicNetworkEdges } from "@/data/mockGaps";

export function TopicNetworkPlaceholder() {
  const groupColors: Record<string, string> = {
    core: "fill-primary stroke-primary",
    retrieval: "fill-blue-500 stroke-blue-500",
    generation: "fill-emerald-500 stroke-emerald-500",
    eval: "fill-amber-500 stroke-amber-500",
    gap: "fill-red-400 stroke-red-400",
  };

  return (
    <div className="relative w-full h-[400px] rounded-xl border bg-card overflow-hidden">
      <svg viewBox="0 0 100 100" className="w-full h-full">
        {/* Edges */}
        {topicNetworkEdges.map((edge, i) => {
          const fromNode = topicNetworkNodes.find((n) => n.id === edge.from);
          const toNode = topicNetworkNodes.find((n) => n.id === edge.to);
          if (!fromNode || !toNode) return null;
          return (
            <motion.line
              key={i}
              x1={fromNode.x}
              y1={fromNode.y}
              x2={toNode.x}
              y2={toNode.y}
              className="stroke-border"
              strokeWidth="0.3"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.6 }}
              transition={{ duration: 0.8, delay: 0.3 + i * 0.05 }}
            />
          );
        })}

        {/* Nodes */}
        {topicNetworkNodes.map((node, i) => (
          <motion.g key={node.id}
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.1 + i * 0.06, type: "spring" }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.size / 8}
              className={cn(groupColors[node.group] || "fill-muted stroke-muted-foreground", "opacity-20")}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={node.size / 12}
              className={cn(groupColors[node.group] || "fill-muted stroke-muted-foreground", "opacity-80")}
            />
            <text
              x={node.x}
              y={node.y + node.size / 6 + 2}
              textAnchor="middle"
              className="fill-foreground text-[2.5px] font-medium"
            >
              {node.label}
            </text>
          </motion.g>
        ))}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-primary" /> Core</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" /> Retrieval</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Generation</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" /> Gaps</span>
      </div>
    </div>
  );
}
