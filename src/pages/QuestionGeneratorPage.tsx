import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { HelpCircle, Sparkles, Copy, CheckCheck, RefreshCw, Download, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const mockQuestions = [
  {
    question: "How can multimodal retrieval be integrated into RAG pipelines to process both textual and visual scientific content?",
    quality: 94,
    type: "Exploratory",
  },
  {
    question: "What is the impact of embedding model choice on the factual accuracy of RAG-generated scientific summaries?",
    quality: 91,
    type: "Comparative",
  },
  {
    question: "To what extent can retrieval-augmented generation reduce hallucination rates in domain-specific scientific question answering?",
    quality: 88,
    type: "Evaluative",
  },
  {
    question: "How do hybrid retrieval strategies combining dense and sparse methods affect the coverage of literature reviews?",
    quality: 86,
    type: "Methodological",
  },
  {
    question: "What are the scalability limitations of current RAG architectures when applied to large-scale scientific knowledge bases?",
    quality: 83,
    type: "Critical",
  },
  {
    question: "Can temporal-aware retrieval mechanisms improve the relevance of citations in rapidly evolving research fields?",
    quality: 79,
    type: "Hypothesis-driven",
  },
];

export default function QuestionGeneratorPage() {
  const [topicInput, setTopicInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [questions, setQuestions] = useState<typeof mockQuestions>([]);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setQuestions([]);

    // Simulate progressive generation
    for (let i = 0; i < mockQuestions.length; i++) {
      await new Promise((r) => setTimeout(r, 400 + Math.random() * 300));
      setQuestions((prev) => [...prev, mockQuestions[i]!]);
    }
    setIsGenerating(false);
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
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="text-2xl font-bold tracking-tight">Research Question Generator</h2>
        <p className="text-muted-foreground mt-1">
          Enter a topic or abstract and let AI generate novel, high-quality research questions.
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
          <div className="flex items-center gap-3">
            <Button onClick={handleGenerate} disabled={isGenerating} className="gap-2">
              {isGenerating ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                    className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full"
                  />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Generate Questions
                </>
              )}
            </Button>
            {questions.length > 0 && (
              <>
                <Button variant="outline" size="sm" onClick={handleGenerate} className="gap-1.5">
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

      {/* Results */}
      <AnimatePresence>
        {questions.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Generated Questions ({questions.length})</h3>
              {!isGenerating && (
                <Badge variant="success" className="text-xs">
                  {questions.length} questions generated
                </Badge>
              )}
            </div>

            {questions.map((q, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
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
                            <Star className="h-3 w-3 text-amber-500" />
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
    </div>
  );
}
