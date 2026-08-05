import { useState } from "react";
import { motion } from "framer-motion";
import { GitFork, Search, Download, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ResearchGapCard } from "@/components/features/ResearchGapCard";
import { TopicNetworkPlaceholder } from "@/components/features/TopicNetworkPlaceholder";
import { CoverageHeatmap } from "@/components/features/CoverageHeatmap";
import { mockResearchGaps } from "@/data/mockGaps";

export default function ResearchGapPage() {
  const [topic, setTopic] = useState("");
  const [hasAnalyzed, setHasAnalyzed] = useState(true); // Show data by default for demo
  const [severityFilter, setSeverityFilter] = useState("all");

  const filteredGaps =
    severityFilter === "all"
      ? mockResearchGaps
      : mockResearchGaps.filter((g) => g.severity === severityFilter);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="text-2xl font-bold tracking-tight">Research Gap Discovery</h2>
        <p className="text-muted-foreground mt-1">
          Identify unexplored areas, coverage gaps, and future research opportunities in any domain.
        </p>
      </motion.div>

      {/* Topic Input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Enter a research topic (e.g., Retrieval-Augmented Generation)"
            className="pl-10 h-11"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
        <Button size="lg" onClick={() => setHasAnalyzed(true)}>
          <GitFork className="mr-2 h-4 w-4" /> Analyze Gaps
        </Button>
        <Button size="lg" variant="outline">
          <Download className="mr-2 h-4 w-4" /> Export
        </Button>
      </div>

      {hasAnalyzed && (
        <Tabs defaultValue="gaps" className="space-y-6">
          <TabsList>
            <TabsTrigger value="gaps">Gap Analysis</TabsTrigger>
            <TabsTrigger value="network">Topic Network</TabsTrigger>
            <TabsTrigger value="heatmap">Coverage Heatmap</TabsTrigger>
          </TabsList>

          {/* Gap Cards */}
          <TabsContent value="gaps" className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select value={severityFilter} onValueChange={setSeverityFilter}>
                  <SelectTrigger className="w-40 h-8">
                    <SelectValue placeholder="Filter by priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    <SelectItem value="high">High Priority</SelectItem>
                    <SelectItem value="medium">Medium Priority</SelectItem>
                    <SelectItem value="low">Low Priority</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Badge variant="secondary">{filteredGaps.length} gaps identified</Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {filteredGaps.map((gap, i) => (
                <ResearchGapCard key={gap.id} gap={gap} index={i} />
              ))}
            </div>
          </TabsContent>

          {/* Topic Network */}
          <TabsContent value="network">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Topic Relationship Network</CardTitle>
                </CardHeader>
                <CardContent>
                  <TopicNetworkPlaceholder />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* Heatmap */}
          <TabsContent value="heatmap">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Research Coverage Heatmap</CardTitle>
                </CardHeader>
                <CardContent>
                  <CoverageHeatmap />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
