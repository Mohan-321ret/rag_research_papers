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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { ragWorkflowSteps, mockChatHistory, mockAIResponse, sampleQuestions } from "@/data/mockChat";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: { id: string; title: string; relevance: number }[];
  isStreaming?: boolean;
  workflowStep?: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});
  const [currentWorkflowStep, setCurrentWorkflowStep] = useState(-1);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentWorkflowStep, scrollToBottom]);

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 150) + "px";
  };

  const simulateRAGWorkflow = async () => {
    // Step through each workflow stage
    for (let i = 0; i < ragWorkflowSteps.length; i++) {
      setCurrentWorkflowStep(i);
      await new Promise((r) => setTimeout(r, ragWorkflowSteps[i]!.duration));
    }
    setCurrentWorkflowStep(-1);

    // Add the AI response
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: mockAIResponse.content,
        sources: mockAIResponse.sources,
      },
    ]);
    setIsLoading(false);
  };

  const handleSubmit = async (question?: string) => {
    const q = (question || input).trim();
    if (!q || isLoading) return;

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setIsLoading(true);
    await simulateRAGWorkflow();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Chat History Sidebar */}
      <div className="hidden lg:flex w-64 flex-col border-r bg-muted/30">
        <div className="p-3">
          <Button variant="outline" className="w-full justify-start gap-2" onClick={() => setMessages([])}>
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
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

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 && !isLoading ? (
              /* Empty State */
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center min-h-[60vh]"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-purple-600 text-white mb-6 shadow-lg">
                  <Sparkles className="h-8 w-8" />
                </div>
                <h2 className="text-2xl font-bold mb-2">How can I help with your research?</h2>
                <p className="text-muted-foreground text-center max-w-md mb-8">
                  Ask questions about scientific papers. I'll search the knowledge base, retrieve relevant documents, and generate answers with citations.
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
              /* Messages List */
              <div className="space-y-6">
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className={cn("flex gap-4", msg.role === "user" ? "justify-end" : "")}
                  >
                    {msg.role === "assistant" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white">
                        <Sparkles className="h-4 w-4" />
                      </div>
                    )}
                    <div className={cn("max-w-[85%] space-y-3", msg.role === "user" ? "order-first" : "")}>
                      <div
                        className={cn(
                          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                          msg.role === "user"
                            ? "bg-primary text-primary-foreground ml-auto rounded-br-md"
                            : "bg-muted rounded-bl-md"
                        )}
                      >
                        {msg.role === "assistant" ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            {msg.content.split("\n").map((line, li) => {
                              if (line.startsWith("## ")) return <h3 key={li} className="text-base font-semibold mt-4 mb-2">{line.slice(3)}</h3>;
                              if (line.startsWith("**") && line.endsWith("**")) return <p key={li} className="font-semibold mt-2">{line.slice(2, -2)}</p>;
                              if (line.startsWith("- ")) return <div key={li} className="flex gap-2 ml-2"><span className="text-primary mt-0.5">•</span><span>{line.slice(2)}</span></div>;
                              if (line.startsWith("|")) return <p key={li} className="font-mono text-xs">{line}</p>;
                              if (line.trim() === "") return <div key={li} className="h-2" />;
                              return <p key={li}>{line}</p>;
                            })}
                          </div>
                        ) : (
                          msg.content
                        )}
                      </div>

                      {/* Sources */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="space-y-2">
                          <button
                            onClick={() => setExpandedSources((prev) => ({ ...prev, [i]: !prev[i] }))}
                            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                          >
                            {expandedSources[i] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            {msg.sources.length} sources cited
                          </button>
                          <AnimatePresence>
                            {expandedSources[i] && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="space-y-2 overflow-hidden"
                              >
                                {msg.sources.map((src, si) => (
                                  <Card key={si} className="p-3">
                                    <div className="flex items-start justify-between gap-2">
                                      <div className="flex-1 min-w-0">
                                        <p className="text-xs font-medium truncate">{src.title}</p>
                                      </div>
                                      <div className="flex items-center gap-2 shrink-0">
                                        <Badge variant="secondary" className="text-xs">
                                          {(src.relevance * 100).toFixed(0)}% match
                                        </Badge>
                                        <ExternalLink className="h-3 w-3 text-muted-foreground" />
                                      </div>
                                    </div>
                                  </Card>
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </div>
                    {msg.role === "user" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                        <User className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </motion.div>
                ))}

                {/* Workflow Steps */}
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-4"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-purple-600 text-white">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div className="space-y-3 flex-1">
                      {ragWorkflowSteps.map((step, si) => (
                        <motion.div
                          key={si}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{
                            opacity: si <= currentWorkflowStep ? 1 : 0.3,
                            x: 0,
                          }}
                          transition={{ duration: 0.3, delay: si * 0.1 }}
                          className={cn(
                            "flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm",
                            si === currentWorkflowStep
                              ? "bg-primary/10 text-primary font-medium"
                              : si < currentWorkflowStep
                              ? "text-muted-foreground line-through"
                              : "text-muted-foreground/50"
                          )}
                        >
                          <span className="text-base">{step.icon}</span>
                          <span>{step.label}</span>
                          {si === currentWorkflowStep && (
                            <motion.div
                              animate={{ rotate: 360 }}
                              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                              className="ml-auto h-4 w-4 border-2 border-primary/30 border-t-primary rounded-full"
                            />
                          )}
                          {si < currentWorkflowStep && (
                            <span className="ml-auto text-emerald-500 text-xs">✓</span>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Bar */}
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
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Press Enter to send · Shift+Enter for new line · Responses are generated using RAG pipeline
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
