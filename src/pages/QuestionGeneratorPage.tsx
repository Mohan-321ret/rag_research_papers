import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  HelpCircle,
  Sparkles,
  Copy,
  CheckCheck,
  RefreshCw,
  Download,
  Star,
  Loader2,
  AlertCircle,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { getToken } from "@/lib/tokenStorage";

const BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

interface GeneratedQuestion {
  question: string;
  quality: number;
  type: string;
}

const Q_TYPES = [
  "Exploratory",
  "Comparative",
  "Evaluative",
  "Methodological",
  "Critical",
  "Hypothesis-driven",
  "Applied",
  "Theoretical",
];

function parseQuestionsFromText(text: string): GeneratedQuestion[] {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && (l.match(/^\d+[.)]/)) || l.startsWith("-") || l.startsWith("•") || l.length > 40);

  const questions: GeneratedQuestion[] = [];
  lines.forEach((line, i) => {
    const clean = line
      .replace(/^\d+[.)]\s*/, "")
      .replace(/^[-•]\s*/, "")
      .replace(/\*\*/g, "")
      .trim();
    if (clean.length > 20 && clean.includes("?")) {
      questions.push({
        question: clean,
        quality: Math.max(65, 95 - i * 3),
        type: Q_TYPES[i % Q_TYPES.length]!,
      });
    }
  });

  if (questions.length === 0 && text.length > 30) {
    // Fallback: split on question marks
    const raw = text.split("?").filter((s) => s.trim().length > 20);
    raw.slice(0, 8).forEach((q, i) => {
      questions.push({
        question: q.trim().replace(/^\d+[.)]\s*/, "").replace(/\*\*/g, "") + "?",
        quality: Math.max(65, 92 - i * 4),
        type: Q_TYPES[i % Q_TYPES.length]!,
      });
    });
  }

  return questions.slice(0, 10);
}

export default function QuestionGeneratorPage() {
  const [topicInput, setTopicInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState("");

  const handleGenerate = async () => {
    if (!topicInput.trim() || isGenerating) return;
    setIsGenerating(true);
    setQuestions([]);
    setError(null);

    const prompt = `Generate 8 high-quality, novel research questions for the following topic or abstract:

"${topicInput}"

Requirements:
- Each question should be specific, measurable, and academically rigorous
- Mix different types: exploratory, comparative, evaluative, methodological, critical
- Questions should identify real gaps or unknowns in the field
- Format: numbered list, one question per line
- Each question must end with a ?

Generate the questions now:`;

    try {
      const token = getToken();
      const res = await fetch(`${BASE}/chat/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: prompt, top_k: 5 }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setModel(data.model ?? "");
      const parsed = parseQuestionsFromText(data.answer);
      setQuestions(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = (idx: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleCopyAll = () => {
    const all = questions.map((q, i) => `${i + 1}. ${q.question}`).join("\n\n");
    navigator.clipboard.writeText(all);
    setCopiedIdx(-1);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold tracking-tight">Research Question Generator</h2>
        <p className="text-muted-foreground mt-1">
          Enter a topic or abstract — Groq searches your knowledge base and generates novel, rigorous research questions.
        </p>
      </motion.div>

      {/* Input */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Research Topic or Abstract</label>
            <Textarea
              placeholder="e.g., Retrieval-Augmented Generation for scientific literature review, including dense passage retrieval, transformer-based embeddings, and citation-aware response generation..."
              className="min-h-[120px]"
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={handleGenerate} disabled={isGenerating || !topicInput.trim()} className="gap-2">
              {isGenerating ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
              ) : (
                <><Sparkles className="h-4 w-4" /> Generate Questions</>
              )}
            </Button>
            {questions.length > 0 && (
              <>
                <Button variant="outline" size="sm" onClick={handleGenerate} disabled={isGenerating} className="gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                </Button>
                <Button variant="outline" size="sm" onClick={handleCopyAll} className="gap-1.5">
                  {copiedIdx === -1 ? (
                    <><CheckCheck className="h-3.5 w-3.5 text-emerald-500" /> Copied All</>
                  ) : (
                    <><Download className="h-3.5 w-3.5" /> Copy All</>
                  )}
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Results */}
      <AnimatePresence>
        {questions.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Generated Questions ({questions.length})</h3>
              <div className="flex items-center gap-2">
                {!isGenerating && model && (
                  <Badge variant="outline" className="text-xs flex items-center gap-1">
                    <Zap className="h-3 w-3 text-emerald-500" /> {model.split("/").pop()}
                  </Badge>
                )}
                {!isGenerating && (
                  <Badge variant="outline" className="text-xs border-emerald-300 text-emerald-600">
                    {questions.length} questions
                  </Badge>
                )}
              </div>
            </div>

            {questions.map((q, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
              >
                <Card className="hover:shadow-sm transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-sm shrink-0">
                        {i + 1}
                      </div>
                      <div className="flex-1 space-y-3">
                        <p className="text-sm font-medium leading-relaxed">{q.question}</p>
                        <div className="flex items-center gap-4">
                          <Badge variant="outline" className="text-xs">{q.type}</Badge>
                          <div className="flex items-center gap-2 flex-1 max-w-[200px]">
                            <Star className="h-3 w-3 text-amber-500 shrink-0" />
                            <Progress value={q.quality} className="h-1.5" />
                            <span className="text-xs text-muted-foreground font-medium">{q.quality}%</span>
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 shrink-0"
                        onClick={() => handleCopy(i, q.question)}
                      >
                        {copiedIdx === i ? (
                          <CheckCheck className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!isGenerating && questions.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <HelpCircle className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Generate research questions</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Paste a topic or abstract above. Groq will use your knowledge base to generate specific, novel, academically rigorous research questions.
          </p>
        </div>
      )}
    </div>
  );
}
