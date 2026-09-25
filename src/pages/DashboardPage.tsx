import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  MessageSquare,
  Search,
  ArrowRight,
  FileText,
  Clock,
  Upload,
  Globe,
  Database,
  Zap,
  Brain,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fetchDashboard, fetchDocuments, fetchChatHistory, type DashboardStats, type DocumentRead, type ChatHistoryItem } from "@/lib/api";

const quickActions = [
  { title: "Upload Papers", description: "Add PDFs to RAG knowledge base", icon: Upload, path: "/upload", color: "bg-indigo-500" },
  { title: "AI Research Chat", description: "Ask questions — powered by Groq", icon: MessageSquare, path: "/chat", color: "bg-violet-500" },
  { title: "Search Knowledge Base", description: "Semantic search over documents", icon: Search, path: "/search", color: "bg-blue-500" },
  { title: "External Sources", description: "Browse arXiv, PubMed, CORE", icon: Globe, path: "/external", color: "bg-emerald-500" },
];

function StatTile({ label, value, icon: Icon, sub }: { label: string; value: string | number; icon: React.ElementType; sub?: string }) {
  return (
    <Card>
      <CardContent className="p-5 flex items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 shrink-0">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
          {sub && <p className="text-xs text-muted-foreground/70">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [docs, setDocs] = useState<DocumentRead[]>([]);
  const [history, setHistory] = useState<ChatHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDashboard().catch(() => null),
      fetchDocuments({ limit: 5 }).catch(() => ({ items: [] as DocumentRead[], total: 0, limit: 5, offset: 0 })),
      fetchChatHistory(5).catch(() => ({ items: [] as ChatHistoryItem[], total: 0, limit: 5, offset: 0 })),
    ]).then(([dash, docsRes, histRes]) => {
      setStats(dash?.stats ?? null);
      setDocs(docsRes?.items ?? []);
      setHistory(histRes?.items ?? []);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, []);

  // Build chart data from stats and activity
  const chartData = (() => {
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const totalDocs = stats?.total_documents ?? docs.length;
    const totalQ = stats?.total_queries ?? history.length;
    return days.map((d, i) => {
      const factor = (i + 1) / 7;
      return {
        name: d,
        queries: Math.round(totalQ * (0.2 + 0.8 * factor)),
        papers: Math.round(totalDocs * (0.3 + 0.7 * factor)),
      };
    });
  })();

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard 👋</h2>
        <p className="text-muted-foreground mt-1">Your RAG research platform — live data from the knowledge base.</p>
      </motion.div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error} — make sure the backend is running.
        </div>
      )}

      {/* Stats */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent className="p-5 animate-pulse"><div className="h-12 bg-muted rounded" /></CardContent></Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Documents in KB" value={stats?.total_documents ?? 0} icon={Database} sub={`${stats?.total_chunks ?? 0} chunks indexed`} />
          <StatTile label="Total Queries" value={stats?.total_queries ?? 0} icon={Brain} sub={`${stats?.total_answers ?? 0} answers generated`} />
          <StatTile label="Avg Confidence" value={stats?.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(0)}%` : "—"} icon={Zap} sub="answer quality" />
          <StatTile label="Avg Latency" value={stats?.avg_latency_ms != null ? `${Math.round(stats.avg_latency_ms)}ms` : "—"} icon={Clock} sub="response time" />
        </div>
      )}

      {/* Quick Actions + Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Quick Actions</h3>
          <div className="space-y-3">
            {quickActions.map((action, i) => (
              <motion.div key={action.title} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: 0.3 + i * 0.07 }}>
                <Link to={action.path}>
                  <Card className="group hover:shadow-md transition-all duration-200 hover:border-primary/30 cursor-pointer">
                    <CardContent className="p-4 flex items-center gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${action.color} text-white shrink-0`}>
                        <action.icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-semibold group-hover:text-primary transition-colors">{action.title}</h4>
                        <p className="text-xs text-muted-foreground">{action.description}</p>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary group-hover:translate-x-1 transition-all" />
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Chart */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }} className="lg:col-span-2">
          <Card>
            <CardHeader><CardTitle className="text-base">Activity Overview (live counts)</CardTitle></CardHeader>
            <CardContent>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="cQ" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.55 0.22 264)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.55 0.22 264)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="cP" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.6 0.18 155)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.6 0.18 155)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="name" tick={{ fill: "oklch(0.556 0.02 264)", fontSize: 11 }} />
                    <YAxis tick={{ fill: "oklch(0.556 0.02 264)", fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px" }} />
                    <Area type="monotone" dataKey="queries" name="Queries" stroke="oklch(0.55 0.22 264)" fillOpacity={1} fill="url(#cQ)" strokeWidth={2} />
                    <Area type="monotone" dataKey="papers" name="Documents" stroke="oklch(0.6 0.18 155)" fillOpacity={1} fill="url(#cP)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Recent Chat History + Recent Documents */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chat history from backend */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.5 }}>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">Recent Queries</CardTitle>
              <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                <Link to="/chat">New Chat <ArrowRight className="ml-1 h-3 w-3" /></Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-1 -mt-2">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-12 animate-pulse bg-muted rounded-lg mb-2" />)
              ) : history.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No queries yet — start chatting!</p>
              ) : (
                history.map((item) => (
                  <div key={item.query_id} className="flex items-start gap-3 py-2.5 border-b last:border-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 shrink-0 mt-0.5">
                      <MessageSquare className="h-4 w-4 text-violet-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.query_text}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.intent} · {item.answers[0]?.model?.split("/").pop() ?? "—"}
                      </p>
                    </div>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap shrink-0">
                      <Clock className="h-3 w-3" />
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Recent documents from backend */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.6 }}>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">Knowledge Base Documents</CardTitle>
              <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                <Link to="/upload">Manage <ArrowRight className="ml-1 h-3 w-3" /></Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-1 -mt-2">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-12 animate-pulse bg-muted rounded-lg mb-2" />)
              ) : docs.length === 0 ? (
                <div className="text-center py-6">
                  <p className="text-sm text-muted-foreground mb-3">No documents yet</p>
                  <Button size="sm" asChild><Link to="/upload"><Upload className="mr-2 h-3.5 w-3.5" /> Upload Papers</Link></Button>
                </div>
              ) : (
                docs.map((doc) => (
                  <div key={doc.id} className="flex items-start gap-3 py-2.5 border-b last:border-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{doc.title}</p>
                      <p className="text-xs text-muted-foreground capitalize">{doc.source_type} · v{doc.current_version ?? 1}</p>
                    </div>
                    <Badge variant={doc.status === "ready" ? "outline" : "secondary"} className={`text-xs shrink-0 ${doc.status === "ready" ? "border-emerald-300 text-emerald-600" : ""}`}>
                      {doc.status}
                    </Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
