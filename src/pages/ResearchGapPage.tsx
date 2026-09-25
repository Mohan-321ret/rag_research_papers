import { useState } from "react";
import { motion } from "framer-motion";
import {
  GitFork,
  Search,
  Loader2,
  AlertCircle,
  Sparkles,
  ChevronRight,
  Zap,
  BookOpen,
  Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getToken } from "@/lib/tokenStorage";

const BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

interface Gap {
  title: string;
  description: string;
  severity: "high" | "medium" | "low";
  suggestedApproach: string;
  relatedTopics: string[];
}

function parsedGapsFromText(text: string, topic: string): Gap[] {
  // Parse structured output from LLM into Gap cards
  const blocks = text.split(/\n(?=\d+\.|\*\*Gap|\*\*\d|\n##)/g).filter(Boolean);

  if (blocks.length === 0) {
    return [{
      title: `Research Gaps in "${topic}"`,
      description: text.slice(0, 600),
      severity: "high",
      suggestedApproach: "See full analysis above.",
      relatedTopics: [topic],
    }];
  }

  return blocks.slice(0, 6).map((block, i) => {
    const lines = block.split("\n").filter(Boolean);
    const titleLine = lines.find((l) => l.match(/^\d+\.|^\*\*|^##/)) ?? lines[0] ?? `Gap ${i + 1}`;
    const title = titleLine.replace(/^[\d.*#\s]+/, "").replace(/\*\*/g, "").trim().slice(0, 100);
    const desc = lines.slice(1, 5).join(" ").replace(/\*\*/g, "").trim().slice(0, 400);
    const severities: ("high" | "medium" | "low")[] = ["high", "medium", "low"];
    return {
      title: title || `Research Gap ${i + 1}`,
      description: desc || "See full analysis.",
      severity: severities[i % 3]!,
      suggestedApproach: lines[lines.length - 1]?.replace(/\*\*/g, "").trim() ?? "Investigate further.",
      relatedTopics: [topic, ...title.split(" ").slice(0, 3)],
    };
  });
}

function SeverityBadge({ s }: { s: "high" | "medium" | "low" }) {
  const map = {
    high: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  };
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[s]}`}>{s} priority</span>;
}

export default function ResearchGapPage() {
  const [topic, setTopic] = useState("");
  const [gaps, setGaps] = useState<Gap[] | null>(null);
  const [rawAnswer, setRawAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState("");

  const analyze = async () => {
    if (!topic.trim() || loading) return;
    setLoading(true);
    setError(null);
    setGaps(null);
    setRawAnswer("");

    const query = `Identify and analyze the key research gaps in the field of "${topic}". 
For each gap, provide: 1) A clear title, 2) Description of what is unknown or underexplored, 
3) Why it matters, 4) Suggested research approach. 
List at least 5 specific gaps based on the papers in the knowledge base and your understanding of the field.
Format each gap with a numbered title and explanation.`;

    try {
      const token = getToken();
      const res = await fetch(`${BASE}/chat/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query, top_k: 8 }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setRawAnswer(data.answer);
      setModel(data.model ?? "");
      setGaps(parsedGapsFromText(data.answer, topic));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold tracking-tight">Research Gap Discovery</h2>
        <p className="text-muted-foreground mt-1">
          Enter a research topic — Groq + your knowledge base will identify unexplored areas and future opportunities.
        </p>
      </motion.div>

      {/* Input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="e.g., Retrieval-Augmented Generation, CRISPR, Quantum ML…"
            className="pl-10 h-11"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && analyze()}
          />
        </div>
        <Button size="lg" onClick={analyze} disabled={loading || !topic.trim()}>
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitFork className="mr-2 h-4 w-4" />}
          {loading ? "Analyzing…" : "Analyze Gaps"}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
          <p className="text-lg font-semibold">Analyzing research gaps…</p>
          <p className="text-sm text-muted-foreground flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-emerald-500" /> Groq is searching your knowledge base and identifying gaps
          </p>
        </motion.div>
      )}

      {/* Results */}
      {gaps !== null && !loading && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h3 className="font-semibold">{gaps.length} gaps identified for "{topic}"</h3>
            </div>
            {model && (
              <Badge variant="outline" className="text-xs flex items-center gap-1">
                <Zap className="h-3 w-3 text-emerald-500" />
                {model.split("/").pop()}
              </Badge>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {gaps.map((gap, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <Card className="h-full hover:border-primary/30 hover:shadow-sm transition-all">
                  <CardContent className="p-5 space-y-3 h-full flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
                          <Lightbulb className="h-4 w-4 text-primary" />
                        </div>
                        <h4 className="font-semibold text-sm leading-tight">{gap.title}</h4>
                      </div>
                      <SeverityBadge s={gap.severity} />
                    </div>
                    <p className="text-sm text-muted-foreground flex-1">{gap.description}</p>
                    <div className="border-t pt-3">
                      <p className="text-xs font-semibold text-muted-foreground mb-1 flex items-center gap-1">
                        <ChevronRight className="h-3 w-3" /> Suggested approach
                      </p>
                      <p className="text-xs text-muted-foreground">{gap.suggestedApproach}</p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {gap.relatedTopics.map((t) => (
                        <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* Full analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BookOpen className="h-4 w-4" /> Full Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm text-muted-foreground whitespace-pre-wrap">
                {rawAnswer}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Empty state */}
      {!loading && gaps === null && !error && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <GitFork className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Discover research gaps</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Enter any research topic above. Groq will search your knowledge base and identify unexplored areas.
          </p>
        </div>
      )}
    </div>
  );
}
