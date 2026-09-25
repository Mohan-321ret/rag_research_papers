import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Plus,
  Sparkles,
  User,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Clock,
  MessageSquare,
  AlertCircle,
  Loader2,
  Zap,
  Brain,
  Search,
  GitMerge,
  CheckCircle2,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { sampleQuestions, mockChatHistory } from "@/data/mockChat";
import { getToken } from "@/lib/tokenStorage";

// ── API types ────────────────────────────────────────────────────────────────

const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

interface CitationItem {
  marker: number;
  document_id: string;
  document_name: string;
  version: number;
  page: number | null;
  chunk_id: string;
  section: string | null;
  score: number;
  snippet: string;
  retrievers: string[];
}

interface ChatQueryResponse {
  answer: string;
  citations: CitationItem[];
  query_id: string;
  answer_id: string;
  model: string;
  retrieved_chunks: number;
  latency_ms: number;
  analysis: { intent: string; normalized_query: string };
  retrieval: {
    route: string;
    reasons: string[];
    retriever_hits: Record<string, number>;
    fallback_used: boolean;
  };
  confidence: number | null;
  hallucination_detected: boolean | null;
}

// ── Workflow steps (visual only — real work is in the backend) ───────────────

const WORKFLOW_STEPS = [
  { icon: Brain, label: "Analyzing query intent…", color: "text-purple-500" },
  { icon: Search, label: "Retrieving relevant chunks…", color: "text-blue-500" },
  { icon: GitMerge, label: "Fusing context & reranking…", color: "text-amber-500" },
  { icon: Sparkles, label: "Generating answer with Groq…", color: "text-emerald-500" },
  { icon: CheckCircle2, label: "Verifying citations…", color: "text-primary" },
];

// ── Message type ─────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: CitationItem[];
  meta?: {
    model: string;
    route: string;
    latency_ms: number;
    confidence: number | null;
    hallucination_detected: boolean | null;
  };
  error?: boolean;
}

// ── Simple markdown renderer ─────────────────────────────────────────────────

function renderMarkdown(text: string) {
  return text.split("\n").map((line, i) => {
    if (line.startsWith("### ")) return <h4 key={i} className="text-sm font-bold mt-3 mb-1">{line.slice(4)}</h4>;
    if (line.startsWith("## ")) return <h3 key={i} className="text-base font-semibold mt-4 mb-2">{line.slice(3)}</h3>;
    if (line.startsWith("# ")) return <h2 key={i} className="text-lg font-bold mt-4 mb-2">{line.slice(2)}</h2>;
    if (line.startsWith("**") && line.endsWith("**")) return <p key={i} className="font-semibold mt-2">{line.slice(2, -2)}</p>;
    if (line.startsWith("- ") || line.startsWith("• ")) return (
      <div key={i} className="flex gap-2 ml-2 my-0.5">
        <span className="text-primary shrink-0 mt-0.5">•</span>
        <span>{line.slice(2)}</span>
      </div>
    );
    if (line.trim() === "") return <div key={i} className="h-2" />;
    return <p key={i} className="my-0.5">{line}</p>;
  });
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [workflowStep, setWorkflowStep] = useState(-1);
  const [includeExternal, setIncludeExternal] = useState(true);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, workflowStep, scrollToBottom]);

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 150) + "px";
  };

  // ── Real API call ──────────────────────────────────────────────────────────

  const callChatAPI = async (query: string): Promise<ChatQueryResponse> => {
    const token = getToken();
    abortRef.current = new AbortController();

    const res = await fetch(`${API_BASE}/chat/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query, top_k: 6, include_external: includeExternal }),
      signal: abortRef.current.signal,
    });

    if (!res.ok) {
      let detail = `Server error (${res.status})`;
      try {
        const data = await res.json();
        if (typeof data?.detail === "string") detail = data.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }

    return res.json();
  };

  // ── Submit handler ─────────────────────────────────────────────────────────

  const handleSubmit = async (question?: string) => {
    const q = (question ?? input).trim();
    if (!q || isLoading) return;

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setIsLoading(true);
    setWorkflowStep(0);

    // Animate through steps while real request runs
    const stepTimer = setInterval(() => {
      setWorkflowStep((s) => {
        if (s >= WORKFLOW_STEPS.length - 1) {
          clearInterval(stepTimer);
          return s;
        }
        return s + 1;
      });
    }, 900);

    try {
      const data = await callChatAPI(q);
      clearInterval(stepTimer);
      setWorkflowStep(-1);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          citations: data.citations,
          meta: {
            model: data.model,
            route: data.retrieval.route,
            latency_ms: data.latency_ms,
            confidence: data.confidence,
            hallucination_detected: data.hallucination_detected,
          },
        },
      ]);
    } catch (err) {
      clearInterval(stepTimer);
      setWorkflowStep(-1);

      if ((err as Error).name === "AbortError") return;

      const msg = err instanceof Error ? err.message : "Unexpected error";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ **Request failed:** ${msg}\n\nMake sure the backend is running at \`${API_BASE}\` and you are logged in.`,
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleNewChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setWorkflowStep(-1);
    setIsLoading(false);
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div className="hidden lg:flex w-64 flex-col border-r bg-muted/30">
        <div className="p-3">
          <Button variant="outline" className="w-full justify-start gap-2" onClick={handleNewChat}>
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>
        <Separator />

        {/* Model pill */}
        <div className="px-3 py-2">
          <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
            <Zap className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 truncate">
                Groq · qwen3.8-27b
              </p>
              <p className="text-xs text-muted-foreground">LLM active</p>
            </div>
          </div>
        </div>

        <Separator />
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {mockChatHistory.map((chat) => (
              <button
                key={chat.id}
                className="w-full text-left rounded-lg px-3 py-2.5 hover:bg-muted transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <MessageSquare className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="text-sm font-medium truncate">{chat.title}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground ml-5">
                  <Clock className="h-3 w-3" />
                  {chat.timestamp}
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* ── Main Chat Area ───────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-3xl px-4 py-6">

            {/* Empty state */}
            {messages.length === 0 && !isLoading ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center min-h-[60vh]"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-purple-600 text-white mb-6 shadow-lg">
                  <Sparkles className="h-8 w-8" />
                </div>
                <h2 className="text-2xl font-bold mb-2">How can I help with your research?</h2>
                <p className="text-muted-foreground text-center max-w-md mb-2">
                  Ask anything — I'll retrieve relevant paper chunks from the knowledge base and generate a grounded answer using <strong>Groq (qwen3.8-27b)</strong>.
                </p>
                <p className="text-xs text-muted-foreground mb-8">
                  Answers cite specific paper sections — no hallucination.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
                  {sampleQuestions.slice(0, 4).map((q, i) => (
                    <motion.button
                      key={i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.08 }}
                      onClick={() => handleSubmit(q)}
                      className="text-left rounded-xl border bg-card p-3.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground hover:border-primary/30 transition-all cursor-pointer"
                    >
                      {q}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <div className="space-y-6">
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "")}
                  >
                    {/* AI avatar */}
                    {msg.role === "assistant" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white mt-0.5">
                        <Sparkles className="h-4 w-4" />
                      </div>
                    )}

                    <div className={cn("max-w-[85%] space-y-2", msg.role === "user" ? "order-first" : "")}>
                      {/* Bubble */}
                      <div
                        className={cn(
                          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                          msg.role === "user"
                            ? "bg-primary text-primary-foreground ml-auto rounded-br-md"
                            : msg.error
                            ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-bl-md"
                            : "bg-muted rounded-bl-md"
                        )}
                      >
                        {msg.role === "assistant" ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            {renderMarkdown(msg.content)}
                          </div>
                        ) : (
                          msg.content
                        )}
                      </div>

                      {/* Meta bar — model, route, latency, confidence */}
                      {msg.meta && (
                        <div className="flex flex-wrap items-center gap-2 px-1">
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Zap className="h-3 w-3 text-emerald-500" />
                            {msg.meta.model.split("/").pop()}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            via <span className="font-medium text-foreground">{msg.meta.route}</span>
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {Math.round(msg.meta.latency_ms)}ms
                          </span>
                          {msg.meta.confidence !== null && (
                            <Badge variant="outline" className="text-xs h-4 px-1.5">
                              {(msg.meta.confidence * 100).toFixed(0)}% confidence
                            </Badge>
                          )}
                          {msg.meta.hallucination_detected === true && (
                            <Badge variant="outline" className="text-xs h-4 px-1.5 border-amber-300 text-amber-600">
                              ⚠ verify sources
                            </Badge>
                          )}
                        </div>
                      )}

                      {/* Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="space-y-2 px-1">
                          <button
                            onClick={() => setExpandedSources((prev) => ({ ...prev, [i]: !prev[i] }))}
                            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {expandedSources[i] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            {msg.citations.length} source{msg.citations.length !== 1 ? "s" : ""} cited
                          </button>
                          <AnimatePresence>
                            {expandedSources[i] && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="space-y-2 overflow-hidden"
                              >
                                {msg.citations.map((cit) => (
                                  <Card key={cit.chunk_id} className="p-3">
                                    <div className="flex items-start justify-between gap-2 mb-1.5">
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1.5">
                                          <span className="text-xs font-bold text-primary">[{cit.marker}]</span>
                                          <p className="text-xs font-medium truncate">{cit.document_name}</p>
                                        </div>
                                        <div className="flex flex-wrap gap-2 mt-0.5">
                                          {cit.page && (
                                            <span className="text-xs text-muted-foreground">p.{cit.page}</span>
                                          )}
                                          {cit.section && (
                                            <span className="text-xs text-muted-foreground truncate max-w-[160px]">§ {cit.section}</span>
                                          )}
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-2 shrink-0">
                                        <Badge variant="secondary" className="text-xs">
                                          {(cit.score * 100).toFixed(0)}%
                                        </Badge>
                                        <ExternalLink className="h-3 w-3 text-muted-foreground" />
                                      </div>
                                    </div>
                                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3 italic">
                                      "{cit.snippet}"
                                    </p>
                                    <div className="flex flex-wrap gap-1 mt-1.5">
                                      {cit.retrievers.map((r) => (
                                        <span key={r} className="text-xs px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground capitalize">
                                          {r}
                                        </span>
                                      ))}
                                    </div>
                                  </Card>
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </div>

                    {/* User avatar */}
                    {msg.role === "user" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted mt-0.5">
                        <User className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </motion.div>
                ))}

                {/* Loading — animated pipeline steps */}
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-3"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white mt-0.5">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                    <div className="space-y-2 flex-1 pt-1">
                      {WORKFLOW_STEPS.map((step, si) => {
                        const Icon = step.icon;
                        const isActive = si === workflowStep;
                        const isDone = si < workflowStep;
                        return (
                          <motion.div
                            key={si}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: si <= workflowStep ? 1 : 0.25, x: 0 }}
                            transition={{ duration: 0.3, delay: si * 0.05 }}
                            className={cn(
                              "flex items-center gap-3 rounded-lg px-4 py-2 text-sm transition-all",
                              isActive
                                ? "bg-primary/10 text-primary font-medium"
                                : isDone
                                ? "text-muted-foreground"
                                : "text-muted-foreground/40"
                            )}
                          >
                            <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : isDone ? "text-emerald-500" : "text-muted-foreground/40")} />
                            <span className={isDone ? "line-through" : ""}>{step.label}</span>
                            {isActive && (
                              <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                                className="ml-auto h-3.5 w-3.5 border-2 border-primary/30 border-t-primary rounded-full"
                              />
                            )}
                            {isDone && (
                              <span className="ml-auto text-emerald-500 text-xs">✓</span>
                            )}
                          </motion.div>
                        );
                      })}
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* ── Input Bar ───────────────────────────────────────────────────── */}
        <div className="border-t bg-background p-4">
          <div className="mx-auto max-w-3xl">
            <div className="relative flex items-end gap-2 rounded-2xl border bg-muted/30 p-2 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 transition-all">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleTextareaChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask a research question..."
                rows={1}
                disabled={isLoading}
                className="flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 max-h-[150px]"
              />
              <Button
                size="icon"
                className="h-9 w-9 rounded-xl shrink-0"
                onClick={() => handleSubmit()}
                disabled={!input.trim() || isLoading}
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground px-1">
              <span className="hidden sm:inline">Press Enter to send · Shift+Enter for new line</span>
              <button
                type="button"
                onClick={() => setIncludeExternal((prev) => !prev)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer",
                  includeExternal
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                    : "bg-muted border-border text-muted-foreground"
                )}
              >
                <Globe className="h-3 w-3" />
                External arXiv Papers: {includeExternal ? "ON" : "OFF"}
              </button>
              <span className="inline-flex items-center gap-1">
                <Zap className="h-3 w-3 text-emerald-500" /> Groq RAG
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
